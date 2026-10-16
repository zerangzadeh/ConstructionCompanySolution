# BONIRA — CEP-042 Execution Prompt

## 1. Package Identity
- CEP ID: `CEP-042`
- CEP Title: `Accounting recognition source adapters`
- Package Type: `INTEGRATION`
- Prompt Class: `IMPLEMENTATION`
- Roadmap Stage: `STG-02 CORE BUILD`
- Roadmap Wave: `RW-03`
- Primary Track: `TRACK-05`
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
- CEP-042 Package Card
- Canonical IMB records
- Canonical CEP Dependency Model
- BONIRA Implementation Roadmap
- BONIRA_ACCOUNTING_RECOGNITION_OWNER_MATRIX
- BONIRA_CONFIGURATION_PROFILE_MATRIX

Package-card source traceability:
- Frozen PDs: `PD-009; PD-011; PD-012; PD-014; PD-030`
- Specifications: `SPEC-002`
- Integration IDs: `INT-A01; INT-A02; INT-A04; INT-C01`
- UI Architecture IDs: `NONE`
- ESS Capability IDs: `NONE`
- Canonical sources: Final Implementation Master Backlog, Dependency Graph, Implementation Roadmap, Codex Implementation Playbook v1.0.
- Repository design baseline: `main @ d75a9334d8e27683159c5f756725c0540651ec43` (read-only inspection).

## 4. Objective
Deliver the canonical outcomes owned by the listed IMBs as one bounded package without expanding authority, scope, roadmap placement or business semantics.

## 5. Primary IMBs
- `IMB-0056` — Inventory → Accounting L2 recognition
- `IMB-0057` — Payroll → Accounting L2 recognition
- `IMB-0059` — Fixed Assets → Accounting L2 recognition
- `IMB-0060` — Direct Expense → Accounting L2 recognition

Only these Primary IMBs define implementation ownership. Secondary/reference IMBs are prerequisites, coordination references or verification targets only.

## 6. Scope
- Integration trigger, idempotency, journal draft mapping, reconciliation.
- Payroll accounting mapping, idempotency, replacement/reversal, reconciliation.
- Asset/depreciation accounting handoff, reversal/correction, reconciliation.
- Expense recognition mapping, idempotency, correction/reversal, audit/reconciliation.

## 7. Explicit Out of Scope
- No posting from inventory existence; Accounting retains final journal authority.
- No draft Payroll recognition; AP/Treasury paths do not repost expense.
- Asset existence alone never posts.
- No generic Expense→AP; reimbursement settlement does not repost expense.
- Any untraced cleanup/refactor/enhancement outside approved IMB outcomes.
- Any actual deployment, migration execution, runtime verification or Human Sign-off unless a later authorized execution package explicitly permits it.

`OUTSIDE APPROVED CEP / IMB SCOPE → RECORD FINDING → DO NOT IMPLEMENT`

## 8. Prerequisite CEPs
- `CEP-008` — source `DEP-0048:IMB-0055→IMB-0056; DEP-0049:IMB-0055→IMB-0057; DEP-0050:IMB-0055→IMB-0059; DEP-0051:IMB-0055→IMB-0060`; strength `MANDATORY`; condition: ALWAYS
- `CEP-021` — source `DEP-0057:IMB-0064→IMB-0060`; strength `MANDATORY`; condition: ALWAYS

Execution-time rule:
`UNMET BLOCKING PREREQUISITE → STOP → BLOCKER-DEPENDENCY → DO NOT IMPLEMENT`

Do not assume a prerequisite is complete because this prompt exists. Check actual prerequisite status at execution time.

## 9. External Dependencies
NONE

Respect phase semantics. A dependency that blocks Activation/Verification/Production does not automatically block Build. Where canonical scope allows build-before-activation, use:
`BUILD MAY PROCEED / ACTIVATION MUST FAIL CLOSED`.

## 10. Entry Gate / Exit Gate
- Entry Gate: `Relevant authority/contract prerequisites`
- Exit Gate: `GATE-05`

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
`one CEP → one branch cep/CEP-042-short-slug → focused commits → verification → review`

Prompt generation itself creates no branch and no commit.

## 12. Expected Code Surfaces
apps/accounting (CONFIRMED directory; exact files UNKNOWN); apps/accounts (CONFIRMED directory; exact files UNKNOWN); apps/expenses (CONFIRMED directory; exact files UNKNOWN); apps/fixed_assets (CONFIRMED directory; exact files UNKNOWN); apps/inventory (CONFIRMED directory; exact files UNKNOWN); apps/payroll (CONFIRMED directory; exact files UNKNOWN)

Treat exact files as repository-grounding results, not assumptions. Do not fabricate paths.

## 13. Implementation Requirements
Upon explicit authorization, implement only the canonical scope below. Use minimum necessary refactoring only when required to safely deliver the approved IMB outcome, and record it in the Change Manifest.

Canonical package scope:
- Integration trigger, idempotency, journal draft mapping, reconciliation.
- Payroll accounting mapping, idempotency, replacement/reversal, reconciliation.
- Asset/depreciation accounting handoff, reversal/correction, reconciliation.
- Expense recognition mapping, idempotency, correction/reversal, audit/reconciliation.

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
NONE

## 18. Financial Authority Requirements
Canonical Financial Impact: YES — Accounting, Payroll, Billing/Expense, Fixed Assets
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

UNIT=REQUIRED; MODEL=NOT APPLICABLE; SERVICE=REQUIRED; PERMISSION=NOT APPLICABLE; TENANT-ISOLATION=NOT APPLICABLE; WORKFLOW=NOT APPLICABLE; INTEGRATION=REQUIRED; MIGRATION=NOT APPLICABLE; UI / TEMPLATE=NOT APPLICABLE; END-TO-END=NOT APPLICABLE; REGRESSION=REQUIRED; RUNTIME VERIFICATION=NOT APPLICABLE; UAT=NOT APPLICABLE; PRODUCTION-CERTIFICATION=NOT APPLICABLE | Canonical basis: IMB-0056:UNIT; DOMAIN; REGRESSION | IMB-0057:UNIT; DOMAIN; REGRESSION | IMB-0059:UNIT; DOMAIN; REGRESSION | IMB-0060:UNIT; DOMAIN; REGRESSION

UTV rule: performance/concurrency and browser/accessibility remain UTV until the applicable runtime verification produces evidence.

## 22. Evidence Plan
Use only package-relevant evidence; no fabricated evidence IDs or results.

CODE DIFF=REQUIRED; TEST OUTPUT=REQUIRED; LINT OUTPUT=REQUIRED; MIGRATION OUTPUT=NOT APPLICABLE; DATA RECONCILIATION=NOT APPLICABLE; PERMISSION TEST=NOT APPLICABLE; TENANT-ISOLATION TEST=NOT APPLICABLE; INTEGRATION TRACE=REQUIRED; TRANSACTION TRACE=REQUIRED; SCREENSHOT=NOT APPLICABLE; UI RUNTIME EVIDENCE=NOT APPLICABLE; LOG / DIAGNOSTIC EVIDENCE=CONDITIONAL; UAT SCENARIO RESULT=NOT APPLICABLE; RESTORE / RECOVERY EVIDENCE=NOT APPLICABLE; PERFORMANCE RESULT=NOT APPLICABLE; ACCESSIBILITY / BROWSER RESULT=NOT APPLICABLE; PRODUCTION-CERTIFICATION EVIDENCE=NOT APPLICABLE | Canonical basis: IMB-0056:Inventory → Accounting L2 recognition: automated integration tests; source identity/version evidence; idempotency/retry test; source→target reconciliation; failure-path evidence; audit/source linkage. | IMB-0057:Payroll → Accounting L2 recognition: automated integration tests; source identity/version evidence; idempotency/retry test; source→target reconciliation; failure-path evidence; audit/source linkage. | IMB-0059:Fixed Assets → Accounting L2 recognition: automated integration tests; source identity/version evidence; idempotency/retry test; source→target reconciliation; failure-path evidence; audit/source linkage. | IMB-0060:Direct Expense → Accounting L2 recognition: automated integration tests; source identity/version evidence; idempotency/retry test; source→target reconciliation; failure-path evidence; audit/source linkage.

Future authorized execution must produce:
- `CEP-042_EXECUTION_MANIFEST.md`
- `CEP-042_ACCEPTANCE_MAPPING.csv`
- `CEP-042_EVIDENCE_MANIFEST.csv`
- `CEP-042_CHANGE_MANIFEST.csv`
- `CEP-042_COMPLETION_REPORT.md`

Evidence IDs must use `CEP-042-EV-001`, `CEP-042-EV-002`, ... and must not be fabricated during prompt generation.

## 23. Acceptance Criteria
Canonical acceptance criteria owned by this CEP; text and conditions are authoritative:

1. `IMB-0056` — 1) `Inventory → Accounting L2 recognition` produces the approved target outcome: INT-A01 uses pinned valuation/source/mapping version and reversal lineage.
   - Planned Verification: PLANNED: SERVICE
   - Planned Evidence: PLANNED: TRANSACTION TRACE; TEST OUTPUT
2. `IMB-0056` — 2) Only the approved source occurrence under INT-A01 can create/update the target effect; source identity/version is retained.
   - Planned Verification: PLANNED: INTEGRATION; SERVICE
   - Planned Evidence: PLANNED: INTEGRATION TRACE; TEST OUTPUT
3. `IMB-0056` — 3) Reprocessing the same source identity/version is idempotent and creates no duplicate target occurrence.
   - Planned Verification: PLANNED: INTEGRATION; SERVICE
   - Planned Evidence: PLANNED: INTEGRATION TRACE; TEST OUTPUT
4. `IMB-0056` — 4) A failed target mutation leaves source authority intact and retains retry/error evidence; retry cannot bypass validation.
   - Planned Verification: PLANNED: INTEGRATION
   - Planned Evidence: PLANNED: INTEGRATION TRACE
5. `IMB-0056` — 5) Authority boundary is preserved: No authority transfer beyond approved source.
   - Planned Verification: PLANNED: SERVICE
   - Planned Evidence: PLANNED: TEST OUTPUT
6. `IMB-0056` — 6) Source/target reconciliation identifies the active source version and corresponding target correction/reversal.
   - Planned Verification: PLANNED: INTEGRATION; SERVICE
   - Planned Evidence: PLANNED: INTEGRATION TRACE; TRANSACTION TRACE; DATA RECONCILIATION; TEST OUTPUT
7. `IMB-0057` — 1) `Payroll → Accounting L2 recognition` produces the approved target outcome: INT-A02 follows Payroll source/version and Recognition Owner Matrix.
   - Planned Verification: PLANNED: SERVICE
   - Planned Evidence: PLANNED: TRANSACTION TRACE; TEST OUTPUT
8. `IMB-0057` — 2) Only the approved source occurrence under INT-A02 can create/update the target effect; source identity/version is retained.
   - Planned Verification: PLANNED: INTEGRATION; SERVICE
   - Planned Evidence: PLANNED: INTEGRATION TRACE; TEST OUTPUT
9. `IMB-0057` — 3) Reprocessing the same source identity/version is idempotent and creates no duplicate target occurrence.
   - Planned Verification: PLANNED: INTEGRATION; SERVICE
   - Planned Evidence: PLANNED: INTEGRATION TRACE; TEST OUTPUT
10. `IMB-0057` — 4) A failed target mutation leaves source authority intact and retains retry/error evidence; retry cannot bypass validation.
   - Planned Verification: PLANNED: INTEGRATION
   - Planned Evidence: PLANNED: INTEGRATION TRACE
11. `IMB-0057` — 5) Authority boundary is preserved: No authority transfer beyond approved source.
   - Planned Verification: PLANNED: SERVICE
   - Planned Evidence: PLANNED: TEST OUTPUT
12. `IMB-0057` — 6) Source/target reconciliation identifies the active source version and corresponding target correction/reversal.
   - Planned Verification: PLANNED: INTEGRATION; SERVICE
   - Planned Evidence: PLANNED: INTEGRATION TRACE; TRANSACTION TRACE; DATA RECONCILIATION; TEST OUTPUT
13. `IMB-0059` — 1) `Fixed Assets → Accounting L2 recognition` produces the approved target outcome: INT-A04 uses asset-book source identity/version and explicit recognition mapping.
   - Planned Verification: PLANNED: INTEGRATION; SERVICE
   - Planned Evidence: PLANNED: INTEGRATION TRACE; TRANSACTION TRACE; TEST OUTPUT
14. `IMB-0059` — 2) Only the approved source occurrence under INT-A04 can create/update the target effect; source identity/version is retained.
   - Planned Verification: PLANNED: INTEGRATION; SERVICE
   - Planned Evidence: PLANNED: INTEGRATION TRACE; TEST OUTPUT
15. `IMB-0059` — 3) Reprocessing the same source identity/version is idempotent and creates no duplicate target occurrence.
   - Planned Verification: PLANNED: INTEGRATION; SERVICE
   - Planned Evidence: PLANNED: INTEGRATION TRACE; TEST OUTPUT
16. `IMB-0059` — 4) A failed target mutation leaves source authority intact and retains retry/error evidence; retry cannot bypass validation.
   - Planned Verification: PLANNED: INTEGRATION
   - Planned Evidence: PLANNED: INTEGRATION TRACE
17. `IMB-0059` — 5) Authority boundary is preserved: No authority transfer beyond approved source.
   - Planned Verification: PLANNED: SERVICE
   - Planned Evidence: PLANNED: TEST OUTPUT
18. `IMB-0059` — 6) Source/target reconciliation identifies the active source version and corresponding target correction/reversal.
   - Planned Verification: PLANNED: INTEGRATION; SERVICE
   - Planned Evidence: PLANNED: INTEGRATION TRACE; TRANSACTION TRACE; DATA RECONCILIATION; TEST OUTPUT
19. `IMB-0060` — 1) `Direct Expense → Accounting L2 recognition` produces the approved target outcome: INT-C01 honors expense source version and financial-boundary policy.
   - Planned Verification: PLANNED: INTEGRATION; SERVICE
   - Planned Evidence: PLANNED: INTEGRATION TRACE; TRANSACTION TRACE; TEST OUTPUT
20. `IMB-0060` — 2) Only the approved source occurrence under INT-C01 can create/update the target effect; source identity/version is retained.
   - Planned Verification: PLANNED: INTEGRATION; SERVICE
   - Planned Evidence: PLANNED: INTEGRATION TRACE; TEST OUTPUT
21. `IMB-0060` — 3) Reprocessing the same source identity/version is idempotent and creates no duplicate target occurrence.
   - Planned Verification: PLANNED: INTEGRATION; SERVICE
   - Planned Evidence: PLANNED: INTEGRATION TRACE; TEST OUTPUT
22. `IMB-0060` — 4) A failed target mutation leaves source authority intact and retains retry/error evidence; retry cannot bypass validation.
   - Planned Verification: PLANNED: INTEGRATION
   - Planned Evidence: PLANNED: INTEGRATION TRACE
23. `IMB-0060` — 5) Authority boundary is preserved: No authority transfer beyond approved source.
   - Planned Verification: PLANNED: SERVICE
   - Planned Evidence: PLANNED: TEST OUTPUT
24. `IMB-0060` — 6) Source/target reconciliation identifies the active source version and corresponding target correction/reversal.
   - Planned Verification: PLANNED: INTEGRATION; SERVICE
   - Planned Evidence: PLANNED: INTEGRATION TRACE; TRANSACTION TRACE; DATA RECONCILIATION; TEST OUTPUT

Acceptance criteria coverage for this CEP: `24 / 24`.

## 24. Definition of Done
- `IMB-0056` DoD: - Target outcome implemented for `Inventory → Accounting L2 recognition` exactly within approved scope. - Source/target contract and lineage implemented. - Idempotency, retry/failure and duplicate prevention implemented. - Reconciliation and audit/source linkage implemented. - Integration/domain/security tests added. - Authority boundary verified.
- `IMB-0057` DoD: - Target outcome implemented for `Payroll → Accounting L2 recognition` exactly within approved scope. - Source/target contract and lineage implemented. - Idempotency, retry/failure and duplicate prevention implemented. - Reconciliation and audit/source linkage implemented. - Integration/domain/security tests added. - Authority boundary verified.
- `IMB-0059` DoD: - Target outcome implemented for `Fixed Assets → Accounting L2 recognition` exactly within approved scope. - Source/target contract and lineage implemented. - Idempotency, retry/failure and duplicate prevention implemented. - Reconciliation and audit/source linkage implemented. - Integration/domain/security tests added. - Authority boundary verified.
- `IMB-0060` DoD: - Target outcome implemented for `Direct Expense → Accounting L2 recognition` exactly within approved scope. - Source/target contract and lineage implemented. - Idempotency, retry/failure and duplicate prevention implemented. - Reconciliation and audit/source linkage implemented. - Integration/domain/security tests added. - Authority boundary verified.

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
- `CEP-042_EXECUTION_MANIFEST.md`
- `CEP-042_ACCEPTANCE_MAPPING.csv`
- `CEP-042_EVIDENCE_MANIFEST.csv`
- `CEP-042_CHANGE_MANIFEST.csv`
- `CEP-042_COMPLETION_REPORT.md`

Evidence IDs must use `CEP-042-EV-001`, `CEP-042-EV-002`, ... and must not be fabricated during prompt generation.

The Completion Report must distinguish pre-existing failures, package-introduced failures, remaining UTV, blockers and downstream readiness.

## 30. Final Execution Verdict Format
At the end of future authorized execution, return exactly one allowed execution outcome:
- `CLOSED — VERIFIED`
- `BLOCKED`
- `FAILED`
- `CANCELLED`
- `SUPERSEDED`

Required checkpoint fields:
- CEP ID: `CEP-042`
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
