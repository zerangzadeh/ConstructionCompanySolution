# BONIRA — CEP-079 Execution Prompt

## 1. Package Identity
- CEP ID: `CEP-079`
- CEP Title: `Representative UAT execution`
- Package Type: `VERIFICATION`
- Prompt Class: `VERIFICATION / UAT`
- Roadmap Stage: `STG-06 REPRESENTATIVE UAT`
- Roadmap Wave: `RW-09`
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
- CEP-079 Package Card
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
- Canonical sources: Final Implementation Master Backlog, Dependency Graph, Implementation Roadmap, Codex Implementation Playbook v1.0.
- Repository design baseline: `main @ d75a9334d8e27683159c5f756725c0540651ec43` (read-only inspection).

## 4. Objective
Deliver the canonical outcomes owned by the listed IMBs as one bounded package without expanding authority, scope, roadmap placement or business semantics.

## 5. Primary IMBs
- `IMB-0110` — Full representative UAT execution

Only these Primary IMBs define implementation ownership. Secondary/reference IMBs are prerequisites, coordination references or verification targets only.

## 6. Scope
- Execute approved UAT catalogue/scenarios and record failures/results.

## 7. Explicit Out of Scope
Execution of the approved Representative UAT defined by this CEP is **IN SCOPE only after explicit CEP authorization** and after all prerequisite, gate, environment, test-data-safety and external-dependency conditions are satisfied.

Explicitly permitted after authorization:
- execution of the approved **44 representative UAT scenarios**;
- capture of scenario pass/fail results, defects, runtime/environment evidence and Scenario→Outcome traceability;
- use of the approved **48 Scenario→IMB mappings** and **30 direct UAT implementation prerequisites**.

`REPRESENTATIVE UAT ≠ EXHAUSTIVE UAT`

`UAT PASS ≠ HUMAN SIGN-OFF`

`UAT PASS ≠ PRODUCTION ACCEPTANCE`

The following remain **OUT OF SCOPE** unless separately authorized:
- expansion beyond the approved representative UAT catalogue;
- inference that all 608 canonical journeys are accepted;
- product-code/configuration/data/policy/architecture remediation merely to force a passing scenario;
- production deployment or production cutover;
- mutation of production business data outside the approved UAT plan;
- Human Sign-off;
- production acceptance.

`VERIFICATION FINDING → RECORD FINDING → PASS / FAIL / PARTIAL / UTV AS EVIDENCE SUPPORTS → DO NOT SILENTLY REMEDIATE`

If remediation is required: `REMEDIATION → SEPARATE AUTHORIZED IMPLEMENTATION ACTION`.

`OUTSIDE APPROVED CEP / IMB SCOPE → RECORD FINDING → DO NOT IMPLEMENT`

Human Sign-off remains outside Codex authority and must never be granted or inferred from successful execution of this CEP.

## 8. Prerequisite CEPs
- `CEP-001` — source `DEP-0113:IMB-0001→IMB-0110; DEP-0114:IMB-0002→IMB-0110`; strength `CONDITIONAL`; condition: Required when UAT scenario UAT-CASE-041 is included in the representative UAT execution set.
- `CEP-002` — source `DEP-0115:IMB-0003→IMB-0110`; strength `CONDITIONAL`; condition: Required when UAT scenario UAT-CASE-001 is included in the representative UAT execution set.
- `CEP-003` — source `DEP-0120:IMB-0013→IMB-0110; DEP-0121:IMB-0014→IMB-0110`; strength `CONDITIONAL`; condition: Required when any of UAT scenarios UAT-CASE-009, UAT-CASE-035, UAT-CASE-037, UAT-CASE-040 is included in the representative UAT execution set.; Required when any of UAT scenarios UAT-CASE-016, UAT-CASE-040 is included in the representative UAT execution set.
- `CEP-006` — source `DEP-0131:IMB-0044→IMB-0110`; strength `CONDITIONAL`; condition: Required when UAT scenario UAT-CASE-017 is included in the representative UAT execution set.
- `CEP-007` — source `DEP-0136:IMB-0052→IMB-0110`; strength `CONDITIONAL`; condition: Required when any of UAT scenarios UAT-CASE-021, UAT-CASE-022 is included in the representative UAT execution set.
- `CEP-010` — source `DEP-0139:IMB-0069→IMB-0110`; strength `CONDITIONAL`; condition: Required when UAT scenario UAT-CASE-034 is included in the representative UAT execution set.
- `CEP-011` — source `DEP-0142:IMB-0095→IMB-0110`; strength `CONDITIONAL`; condition: Required when any of UAT scenarios UAT-CASE-006, UAT-CASE-042 is included in the representative UAT execution set.
- `CEP-016` — source `DEP-0116:IMB-0004→IMB-0110; DEP-0119:IMB-0012→IMB-0110`; strength `CONDITIONAL`; condition: Required when any of UAT scenarios UAT-CASE-002, UAT-CASE-007 is included in the representative UAT execution set.; Required when any of UAT scenarios UAT-CASE-010, UAT-CASE-024, UAT-CASE-025, UAT-CASE-027, UAT-CASE-030, UAT-CASE-032, UAT-CASE-035, UAT-CASE-040 is included in the representative UAT execution set.
- `CEP-017` — source `DEP-0122:IMB-0015→IMB-0110`; strength `CONDITIONAL`; condition: Required when UAT scenario UAT-CASE-040 is included in the representative UAT execution set.
- `CEP-018` — source `DEP-0117:IMB-0007→IMB-0110`; strength `CONDITIONAL`; condition: Required when UAT scenario UAT-CASE-004 is included in the representative UAT execution set.
- `CEP-024` — source `DEP-0140:IMB-0076→IMB-0110`; strength `CONDITIONAL`; condition: Required when UAT scenario UAT-CASE-036 is included in the representative UAT execution set.
- `CEP-027` — source `DEP-0141:IMB-0094→IMB-0110`; strength `CONDITIONAL`; condition: Required when any of UAT scenarios UAT-CASE-011, UAT-CASE-044 is included in the representative UAT execution set.
- `CEP-030` — source `DEP-0123:IMB-0018→IMB-0110`; strength `CONDITIONAL`; condition: Required when UAT scenario UAT-CASE-029 is included in the representative UAT execution set.
- `CEP-031` — source `DEP-0124:IMB-0019→IMB-0110`; strength `CONDITIONAL`; condition: Required when UAT scenario UAT-CASE-029 is included in the representative UAT execution set.
- `CEP-032` — source `DEP-0126:IMB-0022→IMB-0110`; strength `CONDITIONAL`; condition: Required when UAT scenario UAT-CASE-026 is included in the representative UAT execution set.
- `CEP-033` — source `DEP-0127:IMB-0023→IMB-0110`; strength `CONDITIONAL`; condition: Required when UAT scenario UAT-CASE-028 is included in the representative UAT execution set.
- `CEP-034` — source `DEP-0128:IMB-0024→IMB-0110`; strength `CONDITIONAL`; condition: Required when UAT scenario UAT-CASE-031 is included in the representative UAT execution set.
- `CEP-040` — source `DEP-0129:IMB-0039→IMB-0110`; strength `CONDITIONAL`; condition: Required when UAT scenario UAT-CASE-012 is included in the representative UAT execution set.
- `CEP-041` — source `DEP-0132:IMB-0045→IMB-0110`; strength `CONDITIONAL`; condition: Required when UAT scenario UAT-CASE-005 is included in the representative UAT execution set.
- `CEP-045` — source `DEP-0125:IMB-0020→IMB-0110`; strength `CONDITIONAL`; condition: Required when any of UAT scenarios UAT-CASE-011, UAT-CASE-043 is included in the representative UAT execution set.
- `CEP-046` — source `DEP-0118:IMB-0011→IMB-0110`; strength `CONDITIONAL`; condition: Required when UAT scenario UAT-CASE-039 is included in the representative UAT execution set.
- `CEP-049` — source `DEP-0130:IMB-0043→IMB-0110`; strength `CONDITIONAL`; condition: Required when UAT scenario UAT-CASE-008 is included in the representative UAT execution set.
- `CEP-060` — source `DEP-0137:IMB-0053→IMB-0110`; strength `CONDITIONAL`; condition: Required when any of UAT scenarios UAT-CASE-019, UAT-CASE-020 is included in the representative UAT execution set.
- `CEP-061` — source `DEP-0138:IMB-0054→IMB-0110`; strength `CONDITIONAL`; condition: Required when UAT scenario UAT-CASE-023 is included in the representative UAT execution set.
- `CEP-064` — source `DEP-0135:IMB-0051→IMB-0110`; strength `CONDITIONAL`; condition: Required when any of UAT scenarios UAT-CASE-003, UAT-CASE-017 is included in the representative UAT execution set.
- `CEP-066` — source `DEP-0133:IMB-0046→IMB-0110`; strength `CONDITIONAL`; condition: Required when UAT scenario UAT-CASE-005 is included in the representative UAT execution set.
- `CEP-067` — source `DEP-0134:IMB-0047→IMB-0110`; strength `CONDITIONAL`; condition: Required when UAT scenario UAT-CASE-003 is included in the representative UAT execution set.

Execution-time rule:
`UNMET BLOCKING PREREQUISITE → STOP → BLOCKER-DEPENDENCY → DO NOT IMPLEMENT`

Do not assume a prerequisite is complete because this prompt exists. Check actual prerequisite status at execution time.

## 9. External Dependencies
- `EXT-0025` — Phase `VERIFICATION`; Blocks Build `NO`; Activation `NO`; Verification `YES`; Production `NO`; Gate `GATE-09`; Fail-closed: NOT EXECUTED

Respect phase semantics. A dependency that blocks Activation/Verification/Production does not automatically block Build. Where canonical scope allows build-before-activation, use:
`BUILD MAY PROCEED / ACTIVATION MUST FAIL CLOSED`.

## 10. Entry Gate / Exit Gate
- Entry Gate: `GATE-09`
- Exit Gate: `GATE-10`

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
`one CEP → one branch cep/CEP-079-short-slug → focused commits → verification → review`

Prompt generation itself creates no branch and no commit.

## 12. Expected Code Surfaces
certification/ (CONFIRMED repository directory; exact files UNKNOWN)

Treat exact files as repository-grounding results, not assumptions. Do not fabricate paths.

## 13. Implementation Requirements
Verify the already-implemented governed outcome. Do not modify product code to make a verification pass. If a defect is found, record it as a finding and BLOCK/FAIL as appropriate; repair requires separate authorized implementation action.
- Execute only the approved Representative UAT boundary: 44 scenarios, 48 Scenario→IMB mappings, 30 direct implementation prerequisites.
- `REPRESENTATIVE UAT ≠ EXHAUSTIVE UAT`.

Canonical package scope:
- Execute approved UAT catalogue/scenarios and record failures/results.

Required internal IMB sequence:
NONE

## 14. Security Requirements
Canonical Security Impact: `NONE`.
- Security Impact: `NONE`
- Applicability detail: NONE
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
- `EXT-0025` — Phase `VERIFICATION`; Blocks Build `NO`; Activation `NO`; Verification `YES`; Production `NO`; Gate `GATE-09`; Fail-closed: NOT EXECUTED

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

UNIT=NOT APPLICABLE; MODEL=NOT APPLICABLE; SERVICE=NOT APPLICABLE; PERMISSION=CONDITIONAL; TENANT-ISOLATION=CONDITIONAL; WORKFLOW=NOT APPLICABLE; INTEGRATION=NOT APPLICABLE; MIGRATION=NOT APPLICABLE; UI / TEMPLATE=NOT APPLICABLE; END-TO-END=REQUIRED; REGRESSION=NOT APPLICABLE; RUNTIME VERIFICATION=REQUIRED; UAT=REQUIRED; PRODUCTION-CERTIFICATION=NOT APPLICABLE | Canonical basis: IMB-0110:UNIT; DOMAIN; REGRESSION

UTV rule: performance/concurrency and browser/accessibility remain UTV until the applicable runtime verification produces evidence.

### Canonical Test Token Reconciliation
Canonical IMB tokens `UNIT; DOMAIN; REGRESSION` refer to upstream implementation evidence expected before UAT. This CEP is the **Representative UAT execution package**, so UAT + END-TO-END + RUNTIME VERIFICATION are the applicable package tests. UNIT/DOMAIN/REGRESSION are not re-run as implementation work merely because the tokens exist; their prerequisite evidence must already be available and is not discarded.
## 22. Evidence Plan
Use only package-relevant evidence; no fabricated evidence IDs or results.

CODE DIFF=NOT APPLICABLE; TEST OUTPUT=CONDITIONAL; LINT OUTPUT=NOT APPLICABLE; MIGRATION OUTPUT=NOT APPLICABLE; DATA RECONCILIATION=NOT APPLICABLE; PERMISSION TEST=NOT APPLICABLE; TENANT-ISOLATION TEST=NOT APPLICABLE; INTEGRATION TRACE=NOT APPLICABLE; TRANSACTION TRACE=NOT APPLICABLE; SCREENSHOT=NOT APPLICABLE; UI RUNTIME EVIDENCE=CONDITIONAL; LOG / DIAGNOSTIC EVIDENCE=CONDITIONAL; UAT SCENARIO RESULT=REQUIRED; RESTORE / RECOVERY EVIDENCE=NOT APPLICABLE; PERFORMANCE RESULT=NOT APPLICABLE; ACCESSIBILITY / BROWSER RESULT=NOT APPLICABLE; PRODUCTION-CERTIFICATION EVIDENCE=NOT APPLICABLE | Canonical basis: IMB-0110:Full representative UAT execution: executed scenario evidence; environment/runtime details; exact code/version; timestamp; measured artifacts; explicit pass/fail record without promoting unexecuted UTV.

Future authorized execution must produce:
- `CEP-079_EXECUTION_MANIFEST.md`
- `CEP-079_ACCEPTANCE_MAPPING.csv`
- `CEP-079_EVIDENCE_MANIFEST.csv`
- `CEP-079_CHANGE_MANIFEST.csv`
- `CEP-079_COMPLETION_REPORT.md`

Evidence IDs must use `CEP-079-EV-001`, `CEP-079-EV-002`, ... and must not be fabricated during prompt generation.

## 23. Acceptance Criteria
Canonical acceptance criteria owned by this CEP; text and conditions are authoritative:

1. `IMB-0110` — 1) `Full representative UAT execution` produces the approved target outcome: Audit20 limitation is replaced by post-remediation runtime UAT evidence without claiming exhaustiveness beyond executed scope.
   - Planned Verification: PLANNED: UAT; RUNTIME VERIFICATION
   - Planned Evidence: PLANNED: UAT SCENARIO RESULT; environment/runtime traceability
2. `IMB-0110` — 2) Later verification defines exact `Full representative UAT execution` scenario, environment and version.
   - Planned Verification: PLANNED: UAT; RUNTIME VERIFICATION
   - Planned Evidence: PLANNED: UAT SCENARIO RESULT; environment/runtime traceability
3. `IMB-0110` — 3) Scenario is executed rather than inferred from static code/documentation.
   - Planned Verification: PLANNED: UAT; RUNTIME VERIFICATION
   - Planned Evidence: PLANNED: UAT SCENARIO RESULT; environment/runtime traceability
4. `IMB-0110` — 4) Measured/result artifacts and timestamps are retained with explicit pass/fail.
   - Planned Verification: PLANNED: UAT; RUNTIME VERIFICATION
   - Planned Evidence: PLANNED: UAT SCENARIO RESULT; environment/runtime traceability
5. `IMB-0110` — 5) Failed scenario remains an open evidence gap, not feature completion.
   - Planned Verification: PLANNED: UAT; RUNTIME VERIFICATION
   - Planned Evidence: PLANNED: UAT SCENARIO RESULT; environment/runtime traceability
6. `IMB-0110` — 6) UTV remains until execution evidence exists.
   - Planned Verification: PLANNED: UAT; RUNTIME VERIFICATION
   - Planned Evidence: PLANNED: UAT SCENARIO RESULT; environment/runtime traceability

Acceptance criteria coverage for this CEP: `6 / 6`.

## 24. Definition of Done
- `IMB-0110` DoD: - Target outcome implemented for `Full representative UAT execution` exactly within approved scope. - Target environment/scenario documented. - Verification execution procedure prepared. - Evidence/pass-fail record format defined. - Item remains NOT EXECUTED until future verification.

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
- `CEP-079_EXECUTION_MANIFEST.md`
- `CEP-079_ACCEPTANCE_MAPPING.csv`
- `CEP-079_EVIDENCE_MANIFEST.csv`
- `CEP-079_CHANGE_MANIFEST.csv`
- `CEP-079_COMPLETION_REPORT.md`

Evidence IDs must use `CEP-079-EV-001`, `CEP-079-EV-002`, ... and must not be fabricated during prompt generation.

The Completion Report must distinguish pre-existing failures, package-introduced failures, remaining UTV, blockers and downstream readiness.

## 30. Final Execution Verdict Format
At the end of future authorized execution, return exactly one allowed execution outcome:
- `CLOSED — VERIFIED`
- `BLOCKED`
- `FAILED`
- `CANCELLED`
- `SUPERSEDED`

Required checkpoint fields:
- CEP ID: `CEP-079`
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
