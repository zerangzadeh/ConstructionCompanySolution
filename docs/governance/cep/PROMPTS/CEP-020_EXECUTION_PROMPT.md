# BONIRA — CEP-020 Execution Prompt

## 1. Package Identity
- CEP ID: `CEP-020`
- CEP Title: `Forecast and budget-control governance`
- Package Type: `DOMAIN-IMPLEMENTATION`
- Prompt Class: `IMPLEMENTATION`
- Roadmap Stage: `STG-02 CORE BUILD`
- Roadmap Wave: `RW-02`
- Primary Track: `TRACK-04`
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
- CEP-020 Package Card
- Canonical IMB records
- Canonical CEP Dependency Model
- BONIRA Implementation Roadmap
- BONIRA_CONFIGURATION_PROFILE_MATRIX

Package-card source traceability:
- Frozen PDs: `PD-020; PD-024`
- Specifications: `SPEC-001; SPEC-004`
- Integration IDs: `NONE`
- UI Architecture IDs: `NONE`
- ESS Capability IDs: `NONE`
- Canonical sources: Final Implementation Master Backlog, Dependency Graph, Implementation Roadmap, Codex Implementation Playbook v1.0.
- Repository design baseline: `main @ d75a9334d8e27683159c5f756725c0540651ec43` (read-only inspection).

## 4. Objective
Deliver the canonical outcomes owned by the listed IMBs as one bounded package without expanding authority, scope, roadmap placement or business semantics.

## 5. Primary IMBs
- `IMB-0040` — Forecast approval and reforecast lifecycle
- `IMB-0042` — Budget overrun explicit control keys

Only these Primary IMBs define implementation ownership. Secondary/reference IMBs are prerequisites, coordination references or verification targets only.

## 6. Scope
- Submit/review/approve-reject/supersede/reforecast with audit/version/as-of.
- Budget-control enforcement around approved business events and config keys.

## 7. Explicit Out of Scope
- Forecast never rewrites Budget automatically.
- No profile-label behavior; no auto-budget mutation.
- Any untraced cleanup/refactor/enhancement outside approved IMB outcomes.
- Any actual deployment, migration execution, runtime verification or Human Sign-off unless a later authorized execution package explicitly permits it.

`OUTSIDE APPROVED CEP / IMB SCOPE → RECORD FINDING → DO NOT IMPLEMENT`

## 8. Prerequisite CEPs
NONE

Execution-time rule:
`UNMET BLOCKING PREREQUISITE → STOP → BLOCKER-DEPENDENCY → DO NOT IMPLEMENT`

Do not assume a prerequisite is complete because this prompt exists. Check actual prerequisite status at execution time.

## 9. External Dependencies
- `EXT-0011` — Phase `ACTIVATION`; Blocks Build `NO`; Activation `YES`; Verification `NO`; Production `NO`; Gate `GATE-02 where user-facing/security applies; GATE-03 (activation only)`; Fail-closed: Build framework may proceed only where canonical IMB permits fail-closed construction; REQUIRED FOR ACTIVATION

Respect phase semantics. A dependency that blocks Activation/Verification/Production does not automatically block Build. Where canonical scope allows build-before-activation, use:
`BUILD MAY PROCEED / ACTIVATION MUST FAIL CLOSED`.

## 10. Entry Gate / Exit Gate
- Entry Gate: `GATE-01; Normal build prerequisites`
- Exit Gate: `GATE-02 where user-facing/security applies; GATE-03 (activation only)`

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
`one CEP → one branch cep/CEP-020-short-slug → focused commits → verification → review`

Prompt generation itself creates no branch and no commit.

## 12. Expected Code Surfaces
config/ (CONFIRMED repository directory; exact files UNKNOWN); apps/projects (CONFIRMED directory; exact files UNKNOWN); apps/workflows (CONFIRMED directory; exact files UNKNOWN); apps/workforce (CONFIRMED directory; exact files UNKNOWN)

Treat exact files as repository-grounding results, not assumptions. Do not fabricate paths.

## 13. Implementation Requirements
Upon explicit authorization, implement only the canonical scope below. Use minimum necessary refactoring only when required to safely deliver the approved IMB outcome, and record it in the Change Manifest.

Canonical package scope:
- Submit/review/approve-reject/supersede/reforecast with audit/version/as-of.
- Budget-control enforcement around approved business events and config keys.

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
Migration Impact = `NONE`.
- Do not create migration evidence, run migration tests, design cutover or perform data reconciliation unless a separate canonical requirement is discovered during repository grounding.
- If repository reality reveals an unavoidable schema migration required solely to implement approved scope, record a finding before proceeding and follow the Playbook; do not silently expand scope.

## 17. Integration Requirements
Preserve approved integration semantics and interaction levels. Financial integrations must not silently escalate authority.

Coordination relationships (non-blocking unless canonical dependency says otherwise):
- `COORD-0007` with `CEP-015` — Guided configuration profiles may suggest explicit budget-control keys, but profile labels never determine the budget rule.; Blocking = `NO`; sync: BONIRA_CONFIGURATION_PROFILE_MATRIX

External dependency phase semantics:
- `EXT-0011` — Phase `ACTIVATION`; Blocks Build `NO`; Activation `YES`; Verification `NO`; Production `NO`; Gate `GATE-02 where user-facing/security applies; GATE-03 (activation only)`; Fail-closed: Build framework may proceed only where canonical IMB permits fail-closed construction; REQUIRED FOR ACTIVATION

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

UNIT=REQUIRED; MODEL=REQUIRED; SERVICE=REQUIRED; PERMISSION=NOT APPLICABLE; TENANT-ISOLATION=NOT APPLICABLE; WORKFLOW=REQUIRED; INTEGRATION=NOT APPLICABLE; MIGRATION=NOT APPLICABLE; UI / TEMPLATE=NOT APPLICABLE; END-TO-END=NOT APPLICABLE; REGRESSION=REQUIRED; RUNTIME VERIFICATION=NOT APPLICABLE; UAT=NOT APPLICABLE; PRODUCTION-CERTIFICATION=NOT APPLICABLE | Canonical basis: IMB-0040:UNIT; DOMAIN; REGRESSION | IMB-0042:UNIT; DOMAIN; REGRESSION

UTV rule: performance/concurrency and browser/accessibility remain UTV until the applicable runtime verification produces evidence.

## 22. Evidence Plan
Use only package-relevant evidence; no fabricated evidence IDs or results.

CODE DIFF=REQUIRED; TEST OUTPUT=REQUIRED; LINT OUTPUT=REQUIRED; MIGRATION OUTPUT=NOT APPLICABLE; DATA RECONCILIATION=NOT APPLICABLE; PERMISSION TEST=NOT APPLICABLE; TENANT-ISOLATION TEST=NOT APPLICABLE; INTEGRATION TRACE=NOT APPLICABLE; TRANSACTION TRACE=NOT APPLICABLE; SCREENSHOT=NOT APPLICABLE; UI RUNTIME EVIDENCE=NOT APPLICABLE; LOG / DIAGNOSTIC EVIDENCE=NOT APPLICABLE; UAT SCENARIO RESULT=NOT APPLICABLE; RESTORE / RECOVERY EVIDENCE=NOT APPLICABLE; PERFORMANCE RESULT=NOT APPLICABLE; ACCESSIBILITY / BROWSER RESULT=NOT APPLICABLE; PRODUCTION-CERTIFICATION EVIDENCE=NOT APPLICABLE | Canonical basis: IMB-0040:Forecast approval and reforecast lifecycle: request/transition tests; authorized/denied actor evidence; status/audit history; governed rejection/cancellation evidence; source-record linkage. | IMB-0042:Budget overrun explicit control keys: domain lifecycle tests; valid/invalid transition evidence; source-of-truth persistence; correction/history evidence; policy-boundary negative tests; audit linkage.

Future authorized execution must produce:
- `CEP-020_EXECUTION_MANIFEST.md`
- `CEP-020_ACCEPTANCE_MAPPING.csv`
- `CEP-020_EVIDENCE_MANIFEST.csv`
- `CEP-020_CHANGE_MANIFEST.csv`
- `CEP-020_COMPLETION_REPORT.md`

Evidence IDs must use `CEP-020-EV-001`, `CEP-020-EV-002`, ... and must not be fabricated during prompt generation.

## 23. Acceptance Criteria
Canonical acceptance criteria owned by this CEP; text and conditions are authoritative:

1. `IMB-0040` — 1) `Forecast approval and reforecast lifecycle` produces the approved target outcome: Existing draft forecast extends through approved lifecycle defined by PD-020.
   - Planned Verification: PLANNED: WORKFLOW
   - Planned Evidence: PLANNED: TEST OUTPUT
2. `IMB-0040` — 2) Authorized initiator can start `Forecast approval and reforecast lifecycle` only when source preconditions are satisfied.
   - Planned Verification: PLANNED: WORKFLOW
   - Planned Evidence: PLANNED: TEST OUTPUT
3. `IMB-0040` — 3) Reviewer/approver actions require existing workflow/role/object assignment; no approval depth is inferred from title.
   - Planned Verification: PLANNED: WORKFLOW
   - Planned Evidence: PLANNED: TEST OUTPUT
4. `IMB-0040` — 4) Each accepted action retains actor/timestamp/source audit linkage.
   - Planned Verification: PLANNED: UNIT
   - Planned Evidence: PLANNED: TEST OUTPUT; CODE DIFF
5. `IMB-0040` — 5) Rejection/cancellation/correction exists only where governing policy permits and preserves history.
   - Planned Verification: PLANNED: WORKFLOW
   - Planned Evidence: PLANNED: TEST OUTPUT
6. `IMB-0040` — 6) Requester-facing status hides confidential reviewer/security metadata.
   - Planned Verification: PLANNED: WORKFLOW
   - Planned Evidence: PLANNED: TEST OUTPUT
7. `IMB-0042` — 1) `Budget overrun explicit control keys` produces the approved target outcome: Approved configuration keys drive behavior and retain override reason/audit.
   - Planned Verification: PLANNED: WORKFLOW
   - Planned Evidence: PLANNED: TEST OUTPUT
8. `IMB-0042` — 2) Valid lifecycle input persists only in the authoritative source: Owning domain remains authoritative..
   - Planned Verification: PLANNED: UNIT
   - Planned Evidence: PLANNED: TEST OUTPUT; CODE DIFF
9. `IMB-0042` — 3) Invalid or policy-absent input fails closed instead of inventing a default.
   - Planned Verification: PLANNED: UNIT
   - Planned Evidence: PLANNED: TEST OUTPUT; CODE DIFF
10. `IMB-0042` — 4) Correction/replacement preserves prior source identity/version where governed.
   - Planned Verification: PLANNED: SERVICE
   - Planned Evidence: PLANNED: TEST OUTPUT
11. `IMB-0042` — 5) Implementation stays within: Budget-control enforcement around approved business events and config keys.
   - Planned Verification: PLANNED: WORKFLOW
   - Planned Evidence: PLANNED: TEST OUTPUT
12. `IMB-0042` — 6) Excluded behavior remains absent: No profile-label behavior; no auto-budget mutation.
   - Planned Verification: PLANNED: UNIT
   - Planned Evidence: PLANNED: TEST OUTPUT; CODE DIFF

Acceptance criteria coverage for this CEP: `12 / 12`.

## 24. Definition of Done
- `IMB-0040` DoD: - Target outcome implemented for `Forecast approval and reforecast lifecycle` exactly within approved scope. - Approved request/transition paths implemented. - Actor/object authorization enforced. - Audit/source history retained. - Cancellation/rejection/correction only where governed. - Workflow/domain/security tests added.
- `IMB-0042` DoD: - Target outcome implemented for `Budget overrun explicit control keys` exactly within approved scope. - Approved rule implemented without hidden defaults. - Authoritative persistence/history implemented. - Invalid/policy-absent paths fail closed. - Domain/negative-path tests added.

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
- `CEP-020_EXECUTION_MANIFEST.md`
- `CEP-020_ACCEPTANCE_MAPPING.csv`
- `CEP-020_EVIDENCE_MANIFEST.csv`
- `CEP-020_CHANGE_MANIFEST.csv`
- `CEP-020_COMPLETION_REPORT.md`

Evidence IDs must use `CEP-020-EV-001`, `CEP-020-EV-002`, ... and must not be fabricated during prompt generation.

The Completion Report must distinguish pre-existing failures, package-introduced failures, remaining UTV, blockers and downstream readiness.

## 30. Final Execution Verdict Format
At the end of future authorized execution, return exactly one allowed execution outcome:
- `CLOSED — VERIFIED`
- `BLOCKED`
- `FAILED`
- `CANCELLED`
- `SUPERSEDED`

Required checkpoint fields:
- CEP ID: `CEP-020`
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
