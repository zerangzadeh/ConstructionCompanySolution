# BONIRA — CEP-001 Execution Prompt

## 1. Package Identity
- CEP ID: `CEP-001`
- CEP Title: `Tenant and object-scope security foundation`
- Package Type: `SECURITY`
- Prompt Class: `IMPLEMENTATION`
- Roadmap Stage: `STG-01 FOUNDATION`
- Roadmap Wave: `RW-01`
- Primary Track: `TRACK-01`
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
- CEP-001 Package Card
- Canonical IMB records
- Canonical CEP Dependency Model
- BONIRA Implementation Roadmap
- BONIRA_CONFIGURATION_PROFILE_MATRIX

Package-card source traceability:
- Frozen PDs: `PD-016`
- Specifications: `NONE`
- Integration IDs: `NONE`
- UI Architecture IDs: `UIA-002; UIA-018; UIA-045`
- ESS Capability IDs: `NONE`
- Canonical sources: Final Implementation Master Backlog, Dependency Graph, Implementation Roadmap, Codex Implementation Playbook v1.0.
- Repository design baseline: `main @ d75a9334d8e27683159c5f756725c0540651ec43` (read-only inspection).

## 4. Objective
Deliver the canonical outcomes owned by the listed IMBs as one bounded package without expanding authority, scope, roadmap placement or business semantics.

## 5. Primary IMBs
- `IMB-0001` — Tenant Admin isolation enforcement
- `IMB-0002` — Unified Company/Project/Site object-scope enforcement

Only these Primary IMBs define implementation ownership. Secondary/reference IMBs are prerequisites, coordination references or verification targets only.

## 6. Scope
- Enforce tenant boundary in admin/service paths; preserve technical break-glass separation.
- Shared scope service/pattern for Company, Project, Site, forms, deep links and search results.

## 7. Explicit Out of Scope
- No new role hierarchy; no platform admin implicit tenant data access.
- Context selection never grants authority.
- Any untraced cleanup/refactor/enhancement outside approved IMB outcomes.
- Any actual deployment, migration execution, runtime verification or Human Sign-off unless a later authorized execution package explicitly permits it.

`OUTSIDE APPROVED CEP / IMB SCOPE → RECORD FINDING → DO NOT IMPLEMENT`

## 8. Prerequisite CEPs
NONE

Execution-time rule:
`UNMET BLOCKING PREREQUISITE → STOP → BLOCKER-DEPENDENCY → DO NOT IMPLEMENT`

Do not assume a prerequisite is complete because this prompt exists. Check actual prerequisite status at execution time.

## 9. External Dependencies
NONE

Respect phase semantics. A dependency that blocks Activation/Verification/Production does not automatically block Build. Where canonical scope allows build-before-activation, use:
`BUILD MAY PROCEED / ACTIVATION MUST FAIL CLOSED`.

## 10. Entry Gate / Exit Gate
- Entry Gate: `Implementation authorization — NOT YET GRANTED`
- Exit Gate: `GATE-01`

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
`one CEP → one branch cep/CEP-001-short-slug → focused commits → verification → review`

Prompt generation itself creates no branch and no commit.

## 12. Expected Code Surfaces
apps/accounts (CONFIRMED directory; exact files UNKNOWN); core/ (CONFIRMED repository directory; exact files UNKNOWN); apps/organizations (CONFIRMED directory; exact files UNKNOWN)

Treat exact files as repository-grounding results, not assumptions. Do not fabricate paths.

## 13. Implementation Requirements
Upon explicit authorization, implement only the canonical scope below. Use minimum necessary refactoring only when required to safely deliver the approved IMB outcome, and record it in the Change Manifest.

Canonical package scope:
- Enforce tenant boundary in admin/service paths; preserve technical break-glass separation.
- Shared scope service/pattern for Company, Project, Site, forms, deep links and search results.

Required internal IMB sequence:
NONE

## 14. Security Requirements
Canonical Security Impact: `MULTIPLE`.
- Security Impact: `MULTIPLE`
- Applicability detail: AUTHORIZATION, SENSITIVE-DATA, TENANT-ISOLATION
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
Canonical UI Impact: `WORKSPACE`.
- UI Impact: `WORKSPACE`
- UI scope detail: WORKSPACE
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

UNIT=REQUIRED; MODEL=NOT APPLICABLE; SERVICE=REQUIRED; PERMISSION=REQUIRED; TENANT-ISOLATION=REQUIRED; WORKFLOW=NOT APPLICABLE; INTEGRATION=NOT APPLICABLE; MIGRATION=NOT APPLICABLE; UI / TEMPLATE=REQUIRED; END-TO-END=NOT APPLICABLE; REGRESSION=REQUIRED; RUNTIME VERIFICATION=NOT APPLICABLE; UAT=NOT APPLICABLE; PRODUCTION-CERTIFICATION=NOT APPLICABLE | Canonical basis: IMB-0001:SECURITY / PERMISSION; DOMAIN; REGRESSION | IMB-0002:SECURITY / PERMISSION; UNIT; DOMAIN; UI; REGRESSION

UTV rule: performance/concurrency and browser/accessibility remain UTV until the applicable runtime verification produces evidence.

## 22. Evidence Plan
Use only package-relevant evidence; no fabricated evidence IDs or results.

CODE DIFF=REQUIRED; TEST OUTPUT=REQUIRED; LINT OUTPUT=REQUIRED; MIGRATION OUTPUT=NOT APPLICABLE; DATA RECONCILIATION=NOT APPLICABLE; PERMISSION TEST=REQUIRED; TENANT-ISOLATION TEST=REQUIRED; INTEGRATION TRACE=NOT APPLICABLE; TRANSACTION TRACE=NOT APPLICABLE; SCREENSHOT=CONDITIONAL; UI RUNTIME EVIDENCE=CONDITIONAL; LOG / DIAGNOSTIC EVIDENCE=NOT APPLICABLE; UAT SCENARIO RESULT=NOT APPLICABLE; RESTORE / RECOVERY EVIDENCE=NOT APPLICABLE; PERFORMANCE RESULT=NOT APPLICABLE; ACCESSIBILITY / BROWSER RESULT=NOT APPLICABLE; PRODUCTION-CERTIFICATION EVIDENCE=NOT APPLICABLE | Canonical basis: IMB-0001:Tenant Admin isolation enforcement: allowed-access; denied-access; cross-tenant/cross-scope; direct URL/API bypass; queryset/object-filtering evidence; sensitive-field test where applicable. | IMB-0002:Unified Company/Project/Site object-scope enforcement: allowed-access; denied-access; cross-tenant/cross-scope; direct URL/API bypass; queryset/object-filtering evidence; sensitive-field test where applicable.

Future authorized execution must produce:
- `CEP-001_EXECUTION_MANIFEST.md`
- `CEP-001_ACCEPTANCE_MAPPING.csv`
- `CEP-001_EVIDENCE_MANIFEST.csv`
- `CEP-001_CHANGE_MANIFEST.csv`
- `CEP-001_COMPLETION_REPORT.md`

Evidence IDs must use `CEP-001-EV-001`, `CEP-001-EV-002`, ... and must not be fabricated during prompt generation.

## 23. Acceptance Criteria
Canonical acceptance criteria owned by this CEP; text and conditions are authoritative:

1. `IMB-0001` — 1) `Tenant Admin isolation enforcement` produces the approved target outcome: Tenant-scoped admin/business actions require explicit tenant authority and object scope.
   - Planned Verification: PLANNED: PERMISSION; TENANT-ISOLATION; SERVICE
   - Planned Evidence: PLANNED: PERMISSION TEST; TENANT-ISOLATION TEST; TEST OUTPUT
2. `IMB-0001` — 2) An actor/object inside approved scope can exercise `Tenant Admin isolation enforcement`.
   - Planned Verification: PLANNED: SERVICE
   - Planned Evidence: PLANNED: TEST OUTPUT
3. `IMB-0001` — 3) The same operation is denied for out-of-scope/cross-tenant objects at backend/queryset/service level.
   - Planned Verification: PLANNED: PERMISSION; TENANT-ISOLATION
   - Planned Evidence: PLANNED: PERMISSION TEST; TENANT-ISOLATION TEST
4. `IMB-0001` — 4) Direct URL/API enforces the same authorization as the normal UI.
   - Planned Verification: PLANNED: PERMISSION
   - Planned Evidence: PLANNED: PERMISSION TEST
5. `IMB-0001` — 5) UI context or navigation visibility never expands authority.
   - Planned Verification: PLANNED: UNIT
   - Planned Evidence: PLANNED: TEST OUTPUT; CODE DIFF
6. `IMB-0001` — 6) Denied access does not disclose protected object existence or sensitive fields.
   - Planned Verification: PLANNED: PERMISSION
   - Planned Evidence: PLANNED: PERMISSION TEST
7. `IMB-0002` — 1) `Unified Company/Project/Site object-scope enforcement` produces the approved target outcome: Backend/queryset/service enforcement matches effective grants everywhere.
   - Planned Verification: PLANNED: SERVICE
   - Planned Evidence: PLANNED: TEST OUTPUT
8. `IMB-0002` — 2) An actor/object inside approved scope can exercise `Unified Company/Project/Site object-scope enforcement`.
   - Planned Verification: PLANNED: SERVICE
   - Planned Evidence: PLANNED: TEST OUTPUT
9. `IMB-0002` — 3) The same operation is denied for out-of-scope/cross-tenant objects at backend/queryset/service level.
   - Planned Verification: PLANNED: PERMISSION; TENANT-ISOLATION
   - Planned Evidence: PLANNED: PERMISSION TEST; TENANT-ISOLATION TEST
10. `IMB-0002` — 4) Direct URL/API enforces the same authorization as the normal UI.
   - Planned Verification: PLANNED: PERMISSION; UI / TEMPLATE
   - Planned Evidence: PLANNED: PERMISSION TEST; SCREENSHOT
11. `IMB-0002` — 5) UI context or navigation visibility never expands authority.
   - Planned Verification: PLANNED: UI / TEMPLATE
   - Planned Evidence: PLANNED: SCREENSHOT
12. `IMB-0002` — 6) Denied access does not disclose protected object existence or sensitive fields.
   - Planned Verification: PLANNED: PERMISSION
   - Planned Evidence: PLANNED: PERMISSION TEST

Acceptance criteria coverage for this CEP: `12 / 12`.

## 24. Definition of Done
- `IMB-0001` DoD: - Target outcome implemented for `Tenant Admin isolation enforcement` exactly within approved scope. - Backend object scope enforced in queryset/service/direct URL/API. - Allowed/denied and cross-tenant tests added. - Sensitive-field behavior verified where applicable. - Security evidence retained by automated tests.
- `IMB-0002` DoD: - Target outcome implemented for `Unified Company/Project/Site object-scope enforcement` exactly within approved scope. - Backend object scope enforced in queryset/service/direct URL/API. - Allowed/denied and cross-tenant tests added. - Sensitive-field behavior verified where applicable. - Security evidence retained by automated tests.

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
- `CEP-001_EXECUTION_MANIFEST.md`
- `CEP-001_ACCEPTANCE_MAPPING.csv`
- `CEP-001_EVIDENCE_MANIFEST.csv`
- `CEP-001_CHANGE_MANIFEST.csv`
- `CEP-001_COMPLETION_REPORT.md`

Evidence IDs must use `CEP-001-EV-001`, `CEP-001-EV-002`, ... and must not be fabricated during prompt generation.

The Completion Report must distinguish pre-existing failures, package-introduced failures, remaining UTV, blockers and downstream readiness.

## 30. Final Execution Verdict Format
At the end of future authorized execution, return exactly one allowed execution outcome:
- `CLOSED — VERIFIED`
- `BLOCKED`
- `FAILED`
- `CANCELLED`
- `SUPERSEDED`

Required checkpoint fields:
- CEP ID: `CEP-001`
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
