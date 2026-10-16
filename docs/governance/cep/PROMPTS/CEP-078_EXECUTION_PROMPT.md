# BONIRA — CEP-078 Execution Prompt

## 1. Package Identity
- CEP ID: `CEP-078`
- CEP Title: `Browser, accessibility and responsive runtime verification`
- Package Type: `VERIFICATION`
- Prompt Class: `VERIFICATION / UAT`
- Roadmap Stage: `STG-05 SYSTEM VERIFICATION`
- Roadmap Wave: `RW-08`
- Primary Track: `TRACK-10`
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
- CEP-078 Package Card
- Canonical IMB records
- Canonical CEP Dependency Model
- BONIRA Implementation Roadmap
- BONIRA_CONFIGURATION_PROFILE_MATRIX

Package-card source traceability:
- Frozen PDs: `NONE`
- Specifications: `NONE`
- Integration IDs: `NONE`
- UI Architecture IDs: `UIA-010; UIA-011`
- ESS Capability IDs: `NONE`
- Canonical sources: Final Implementation Master Backlog, Dependency Graph, Implementation Roadmap, Codex Implementation Playbook v1.0.
- Repository design baseline: `main @ d75a9334d8e27683159c5f756725c0540651ec43` (read-only inspection).

## 4. Objective
Deliver the canonical outcomes owned by the listed IMBs as one bounded package without expanding authority, scope, roadmap placement or business semantics.

## 5. Primary IMBs
- `IMB-0108` — Browser/accessibility/responsive runtime verification

Only these Primary IMBs define implementation ownership. Secondary/reference IMBs are prerequisites, coordination references or verification targets only.

## 6. Scope
- Browser, responsive, keyboard/focus, semantic and accessibility scenarios.

## 7. Explicit Out of Scope
The browser, accessibility and responsive runtime verification explicitly defined by this CEP is **IN SCOPE only after explicit CEP authorization** and after all prerequisite, gate, environment and supported-scope conditions are satisfied.

Explicitly permitted after authorization:
- approved browser verification;
- approved accessibility runtime verification;
- approved responsive UI verification;
- approved runtime/screenshot/accessibility evidence capture within the supported scope.

The following remain **OUT OF SCOPE** unless separately authorized:
- silent UI redesign;
- product-scope expansion;
- rewriting accessibility requirements;
- unrelated UI defect remediation;
- product-code/template/style changes made merely to force a passing result;
- runtime activity outside the approved verification scenario;
- production cutover;
- Human Sign-off or production acceptance.

Previously UTV browser/accessibility runtime evidence remains UTV until executed.

`VERIFICATION FINDING → RECORD FINDING → PASS / FAIL / PARTIAL / UTV AS EVIDENCE SUPPORTS → DO NOT SILENTLY REMEDIATE`

If remediation is required: `REMEDIATION → SEPARATE AUTHORIZED IMPLEMENTATION ACTION`.

`OUTSIDE APPROVED CEP / IMB SCOPE → RECORD FINDING → DO NOT IMPLEMENT`

Human Sign-off remains outside Codex authority and must never be granted or inferred from successful execution of this CEP.

## 8. Prerequisite CEPs
- `CEP-003` — source `DEP-0018:IMB-0013→IMB-0108; DEP-0019:IMB-0014→IMB-0108`; strength `MANDATORY`; condition: ALWAYS
- `CEP-017` — source `DEP-0020:IMB-0015→IMB-0108`; strength `MANDATORY`; condition: ALWAYS

Execution-time rule:
`UNMET BLOCKING PREREQUISITE → STOP → BLOCKER-DEPENDENCY → DO NOT IMPLEMENT`

Do not assume a prerequisite is complete because this prompt exists. Check actual prerequisite status at execution time.

## 9. External Dependencies
- `EXT-0024` — Phase `VERIFICATION`; Blocks Build `NO`; Activation `NO`; Verification `YES`; Production `NO`; Gate `Relevant implementation gate + external verification dependency`; Fail-closed: NOT EXECUTED

Respect phase semantics. A dependency that blocks Activation/Verification/Production does not automatically block Build. Where canonical scope allows build-before-activation, use:
`BUILD MAY PROCEED / ACTIVATION MUST FAIL CLOSED`.

## 10. Entry Gate / Exit Gate
- Entry Gate: `Relevant implementation gate + external verification dependency`
- Exit Gate: `GATE-08`

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
`one CEP → one branch cep/CEP-078-short-slug → focused commits → verification → review`

Prompt generation itself creates no branch and no commit.

## 12. Expected Code Surfaces
certification/ (CONFIRMED repository directory; exact files UNKNOWN); apps/workforce (CONFIRMED directory; exact files UNKNOWN)

Treat exact files as repository-grounding results, not assumptions. Do not fabricate paths.

## 13. Implementation Requirements
Verify the already-implemented governed outcome. Do not modify product code to make a verification pass. If a defect is found, record it as a finding and BLOCK/FAIL as appropriate; repair requires separate authorized implementation action.

Canonical package scope:
- Browser, responsive, keyboard/focus, semantic and accessibility scenarios.

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
NONE

External dependency phase semantics:
- `EXT-0024` — Phase `VERIFICATION`; Blocks Build `NO`; Activation `NO`; Verification `YES`; Production `NO`; Gate `Relevant implementation gate + external verification dependency`; Fail-closed: NOT EXECUTED

## 18. Financial Authority Requirements
NOT APPLICABLE. Do not invent financial posting, reconciliation, accounting-recognition or cash-authority behavior.

## 19. UI Requirements
Canonical UI Impact: `ACCESSIBILITY / RESPONSIVE`.
- UI Impact: `ACCESSIBILITY / RESPONSIVE`
- UI scope detail: ACCESSIBILITY / RESPONSIVE
- UI / Template Test: `REQUIRED`
- Screenshot Evidence: `CONDITIONAL`
- UI Runtime Evidence: `REQUIRED`
- Global BONIRA UI standards govern if UI is touched, but do not themselves create CEP UI impact.
- Preserve Persian-first UX, RTL, Jalali where required, accessibility, responsive behavior, design tokens and workspace boundaries.
- `UI VISIBILITY ≠ AUTHORIZATION`.

## 20. Regulatory / Configuration Requirements
NOT APPLICABLE. Do not infer profile, regulatory or feature-flag semantics.

## 21. Test Plan
Use the corrected CEP-specific applicability exactly; do not replace it with a universal test matrix.

UNIT=NOT APPLICABLE; MODEL=NOT APPLICABLE; SERVICE=NOT APPLICABLE; PERMISSION=NOT APPLICABLE; TENANT-ISOLATION=NOT APPLICABLE; WORKFLOW=NOT APPLICABLE; INTEGRATION=NOT APPLICABLE; MIGRATION=NOT APPLICABLE; UI / TEMPLATE=REQUIRED; END-TO-END=REQUIRED; REGRESSION=NOT APPLICABLE; RUNTIME VERIFICATION=REQUIRED; UAT=NOT APPLICABLE; PRODUCTION-CERTIFICATION=NOT APPLICABLE | Canonical basis: IMB-0108:BROWSER; ACCESSIBILITY; UI; REGRESSION

UTV rule: performance/concurrency and browser/accessibility remain UTV until the applicable runtime verification produces evidence.

### Canonical Test Token Reconciliation
Canonical tokens `BROWSER; ACCESSIBILITY; UI; REGRESSION` remain authoritative expected evidence types. This CEP directly executes browser/accessibility/responsive runtime verification, so `UI / TEMPLATE`, END-TO-END and RUNTIME VERIFICATION are REQUIRED. Generic REGRESSION is not a separate package-wide rerun requirement unless the approved scenario or repository grounding establishes it as necessary.
## 22. Evidence Plan
Use only package-relevant evidence; no fabricated evidence IDs or results.

CODE DIFF=NOT APPLICABLE; TEST OUTPUT=REQUIRED; LINT OUTPUT=NOT APPLICABLE; MIGRATION OUTPUT=NOT APPLICABLE; DATA RECONCILIATION=NOT APPLICABLE; PERMISSION TEST=NOT APPLICABLE; TENANT-ISOLATION TEST=NOT APPLICABLE; INTEGRATION TRACE=NOT APPLICABLE; TRANSACTION TRACE=NOT APPLICABLE; SCREENSHOT=CONDITIONAL; UI RUNTIME EVIDENCE=REQUIRED; LOG / DIAGNOSTIC EVIDENCE=NOT APPLICABLE; UAT SCENARIO RESULT=NOT APPLICABLE; RESTORE / RECOVERY EVIDENCE=NOT APPLICABLE; PERFORMANCE RESULT=NOT APPLICABLE; ACCESSIBILITY / BROWSER RESULT=REQUIRED; PRODUCTION-CERTIFICATION EVIDENCE=NOT APPLICABLE | Canonical basis: IMB-0108:Browser/accessibility/responsive runtime verification: executed scenario evidence; environment/runtime details; exact code/version; timestamp; measured artifacts; explicit pass/fail record without promoting unexecuted UTV.

Future authorized execution must produce:
- `CEP-078_EXECUTION_MANIFEST.md`
- `CEP-078_ACCEPTANCE_MAPPING.csv`
- `CEP-078_EVIDENCE_MANIFEST.csv`
- `CEP-078_CHANGE_MANIFEST.csv`
- `CEP-078_COMPLETION_REPORT.md`

Evidence IDs must use `CEP-078-EV-001`, `CEP-078-EV-002`, ... and must not be fabricated during prompt generation.

## 23. Acceptance Criteria
Canonical acceptance criteria owned by this CEP; text and conditions are authoritative:

1. `IMB-0108` — 1) `Browser/accessibility/responsive runtime verification` produces the approved target outcome: Audit19 static fixes are followed by runtime cross-browser/accessibility evidence.
   - Planned Verification: PLANNED: RUNTIME VERIFICATION; UI / TEMPLATE
   - Planned Evidence: PLANNED: ACCESSIBILITY / BROWSER RESULT; UI RUNTIME EVIDENCE
2. `IMB-0108` — 2) Later verification defines exact `Browser/accessibility/responsive runtime verification` scenario, environment and version.
   - Planned Verification: PLANNED: RUNTIME VERIFICATION; UI / TEMPLATE
   - Planned Evidence: PLANNED: ACCESSIBILITY / BROWSER RESULT; UI RUNTIME EVIDENCE
3. `IMB-0108` — 3) Scenario is executed rather than inferred from static code/documentation.
   - Planned Verification: PLANNED: RUNTIME VERIFICATION; UI / TEMPLATE
   - Planned Evidence: PLANNED: ACCESSIBILITY / BROWSER RESULT; UI RUNTIME EVIDENCE
4. `IMB-0108` — 4) Measured/result artifacts and timestamps are retained with explicit pass/fail.
   - Planned Verification: PLANNED: RUNTIME VERIFICATION; UI / TEMPLATE
   - Planned Evidence: PLANNED: ACCESSIBILITY / BROWSER RESULT; UI RUNTIME EVIDENCE
5. `IMB-0108` — 5) Failed scenario remains an open evidence gap, not feature completion.
   - Planned Verification: PLANNED: RUNTIME VERIFICATION; UI / TEMPLATE
   - Planned Evidence: PLANNED: ACCESSIBILITY / BROWSER RESULT; UI RUNTIME EVIDENCE
6. `IMB-0108` — 6) UTV remains until execution evidence exists.
   - Planned Verification: PLANNED: RUNTIME VERIFICATION; UI / TEMPLATE
   - Planned Evidence: PLANNED: ACCESSIBILITY / BROWSER RESULT; UI RUNTIME EVIDENCE

Acceptance criteria coverage for this CEP: `6 / 6`.

## 24. Definition of Done
- `IMB-0108` DoD: - Target outcome implemented for `Browser/accessibility/responsive runtime verification` exactly within approved scope. - Target environment/scenario documented. - Verification execution procedure prepared. - Evidence/pass-fail record format defined. - Item remains NOT EXECUTED until future verification.

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
- `CEP-078_EXECUTION_MANIFEST.md`
- `CEP-078_ACCEPTANCE_MAPPING.csv`
- `CEP-078_EVIDENCE_MANIFEST.csv`
- `CEP-078_CHANGE_MANIFEST.csv`
- `CEP-078_COMPLETION_REPORT.md`

Evidence IDs must use `CEP-078-EV-001`, `CEP-078-EV-002`, ... and must not be fabricated during prompt generation.

The Completion Report must distinguish pre-existing failures, package-introduced failures, remaining UTV, blockers and downstream readiness.

## 30. Final Execution Verdict Format
At the end of future authorized execution, return exactly one allowed execution outcome:
- `CLOSED — VERIFIED`
- `BLOCKED`
- `FAILED`
- `CANCELLED`
- `SUPERSEDED`

Required checkpoint fields:
- CEP ID: `CEP-078`
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
