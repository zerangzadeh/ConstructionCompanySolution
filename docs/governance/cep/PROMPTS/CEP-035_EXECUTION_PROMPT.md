# BONIRA — CEP-035 Execution Prompt

## 1. Package Identity
- CEP ID: `CEP-035`
- CEP Title: `Price Book versioning and pinned mapping`
- Package Type: `DOMAIN-IMPLEMENTATION`
- Prompt Class: `IMPLEMENTATION`
- Roadmap Stage: `STG-02 CORE BUILD`
- Roadmap Wave: `RW-03`
- Primary Track: `TRACK-03`
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
- CEP-035 Package Card
- Canonical IMB records
- Canonical CEP Dependency Model
- BONIRA Implementation Roadmap
- BONIRA_CONFIGURATION_PROFILE_MATRIX

Package-card source traceability:
- Frozen PDs: `PD-017`
- Specifications: `SPEC-022; SPEC-032`
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
- `IMB-0025` — Governed Price Book source/version engine
- `IMB-0026` — Price Book mapping/version pinning

Only these Primary IMBs define implementation ownership. Secondary/reference IMBs are prerequisites, coordination references or verification targets only.

## 6. Scope
- Price Book model/import/version activation/provenance; fail closed without verified source.
- Mapping identity/version, effective date, remap/supersession, downstream revision linkage.

## 7. Explicit Out of Scope
- No official values invented; no silent replacement of historical versions.
- No automatic remap when a new Price Book version appears.
- Any untraced cleanup/refactor/enhancement outside approved IMB outcomes.
- Production deployment/cutover, irreversible production migration or production data mutation, runtime verification outside this CEP’s required checks, and Human Sign-off remain outside scope unless separately authorized.

`OUTSIDE APPROVED CEP / IMB SCOPE → RECORD FINDING → DO NOT IMPLEMENT`

## 8. Prerequisite CEPs
NONE

Execution-time rule:
`UNMET BLOCKING PREREQUISITE → STOP → BLOCKER-DEPENDENCY → DO NOT IMPLEMENT`

Do not assume a prerequisite is complete because this prompt exists. Check actual prerequisite status at execution time.

## 9. External Dependencies
- `EXT-0002` — Phase `ACTIVATION`; Blocks Build `NO`; Activation `YES`; Verification `NO`; Production `NO`; Gate `GATE-03 (activation only); Wave contract stabilization / relevant domain gate`; Fail-closed: Build framework may proceed only where canonical IMB permits fail-closed construction; NOT YET PROVIDED IN THIS PHASE

Respect phase semantics. A dependency that blocks Activation/Verification/Production does not automatically block Build. Where canonical scope allows build-before-activation, use:
`BUILD MAY PROCEED / ACTIVATION MUST FAIL CLOSED`.

## 10. Entry Gate / Exit Gate
- Entry Gate: `Normal build prerequisites; Prior-wave contract/schema foundations`
- Exit Gate: `GATE-03 (activation only); Wave contract stabilization / relevant domain gate`

Gate state must be checked at execution time. Prompt existence does not satisfy a gate.

## 11. Repository Grounding
At execution start, before product mutation:
1. Confirm current branch/base and record commit SHA.
2. Inspect existing implementation and relevant apps/models/services/templates/endpoints/tests.
3. Inspect migration state only when applicable.
4. Run/record focused baseline checks where practical; separate pre-existing failures.
5. Compare repository reality with this package design.
6. Complete `CEP-035_EXECUTION_MANIFEST.md` with actual execution-time findings.

`REPOSITORY REALITY > DOCUMENT ASSUMPTION`

If repository reality contradicts the package design, record `CEP-035-FINDING-###`; do not silently redesign. If safe execution is impossible, use `BLOCKER-REPOSITORY` or the appropriate blocker and STOP.

Current Git mechanics are governed by `Agents.md` and the Execution Policy:
`default = current local main; no new branch/worktree; no git add/commit/push/merge unless separately and explicitly authorized`.

Prompt existence or CEP completion does not grant Git-write authority.

## 12. Expected Code Surfaces
apps/estimates (CONFIRMED directory; exact files UNKNOWN)

Treat exact files as repository-grounding results, not assumptions. Do not fabricate paths.

## 13. Implementation Requirements
Under the current applicable execution authority, implement only the canonical scope below. Use minimum necessary refactoring only when required to safely deliver the approved IMB outcome, and record it in the Change Manifest.

Canonical package scope:
- Price Book model/import/version activation/provenance; fail closed without verified source.
- Mapping identity/version, effective date, remap/supersession, downstream revision linkage.

Required internal IMB sequence:
- `IMB-0025 → IMB-0026` via `DEP-0023`. Sequence: IMB-0025 → stabilize required contract/outcome → IMB-0026. Stability point: Price Book mapping/version pinning requires governed Price Book source/version identities to exist before BOQ/Estimate rows can pin them.

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
Canonical Migration Impact: `COMPATIBILITY-MIGRATION`.
- Migration Impact: `COMPATIBILITY-MIGRATION`
- Canonical components: COMPATIBILITY-MIGRATION
- Migration Test: `REQUIRED`
- Migration Evidence: `REQUIRED`
- Distinguish Migration Code / Preparation / Execution / Verification / Cutover.
- Bounded non-production migration preparation, tests, rehearsal, execution or verification may proceed only to the extent this canonical package and current applicable authority permit and all required data/environment prerequisites are satisfied.
- Production migration, irreversible production mutation and Production Cutover remain Human-only and require explicit authority for the exact action.

## 17. Integration Requirements
Preserve approved integration semantics and interaction levels. Financial integrations must not silently escalate authority.

Coordination relationships (non-blocking unless canonical dependency says otherwise):
NONE

External dependency phase semantics:
- `EXT-0002` — Phase `ACTIVATION`; Blocks Build `NO`; Activation `YES`; Verification `NO`; Production `NO`; Gate `GATE-03 (activation only); Wave contract stabilization / relevant domain gate`; Fail-closed: Build framework may proceed only where canonical IMB permits fail-closed construction; NOT YET PROVIDED IN THIS PHASE

## 18. Financial Authority Requirements
NOT APPLICABLE. Do not invent financial posting, reconciliation, accounting-recognition or cash-authority behavior.

## 19. UI Requirements
UI Impact = `NONE`.
- Do not invent UI work.
- If implementation unexpectedly touches UI, record a finding; BONIRA Persian-first/RTL/Jalali/accessibility/design-token standards remain governing.

## 20. Regulatory / Configuration Requirements
Regulatory Impact: YES — source/version/effective-date/evidence governance applies; fail closed where authoritative content is absent
- Governed regulatory content must be VERSIONED + EFFECTIVE-DATED + SOURCE-TRACEABLE + ACTIVATION-CONTROLLED.
- No verified authoritative evidence → FAIL CLOSED. Do not invent rates, thresholds, dates or indexed values.

## 21. Test Plan
Use the corrected CEP-specific applicability exactly; do not replace it with a universal test matrix.

UNIT=REQUIRED; MODEL=REQUIRED; SERVICE=REQUIRED; PERMISSION=NOT APPLICABLE; TENANT-ISOLATION=NOT APPLICABLE; WORKFLOW=NOT APPLICABLE; INTEGRATION=NOT APPLICABLE; MIGRATION=REQUIRED; UI / TEMPLATE=NOT APPLICABLE; END-TO-END=NOT APPLICABLE; REGRESSION=REQUIRED; RUNTIME VERIFICATION=NOT APPLICABLE; UAT=NOT APPLICABLE; PRODUCTION-CERTIFICATION=NOT APPLICABLE | Canonical basis: IMB-0025:UNIT; DOMAIN; IMPORT; REGRESSION | IMB-0026:UNIT; DOMAIN; REGRESSION

UTV rule: performance/concurrency and browser/accessibility remain UTV until the applicable runtime verification produces evidence.

## 22. Evidence Plan
Use only package-relevant evidence; no fabricated evidence IDs or results.

CODE DIFF=REQUIRED; TEST OUTPUT=REQUIRED; LINT OUTPUT=REQUIRED; MIGRATION OUTPUT=REQUIRED; DATA RECONCILIATION=REQUIRED; PERMISSION TEST=NOT APPLICABLE; TENANT-ISOLATION TEST=NOT APPLICABLE; INTEGRATION TRACE=NOT APPLICABLE; TRANSACTION TRACE=NOT APPLICABLE; SCREENSHOT=NOT APPLICABLE; UI RUNTIME EVIDENCE=NOT APPLICABLE; LOG / DIAGNOSTIC EVIDENCE=NOT APPLICABLE; UAT SCENARIO RESULT=NOT APPLICABLE; RESTORE / RECOVERY EVIDENCE=NOT APPLICABLE; PERFORMANCE RESULT=NOT APPLICABLE; ACCESSIBILITY / BROWSER RESULT=NOT APPLICABLE; PRODUCTION-CERTIFICATION EVIDENCE=NOT APPLICABLE | Canonical basis: IMB-0025:Governed Price Book source/version engine: domain lifecycle tests; valid/invalid transition evidence; source-of-truth persistence; correction/history evidence; policy-boundary negative tests; audit linkage. | IMB-0026:Price Book mapping/version pinning: domain lifecycle tests; valid/invalid transition evidence; source-of-truth persistence; correction/history evidence; policy-boundary negative tests; audit linkage. Migration/cutover evidence: source preservation; before/after reconciliation; exception handling; historical traceability; rollback/cutover record where applicable.

Execution must produce:
- `CEP-035_EXECUTION_MANIFEST.md`
- `CEP-035_ACCEPTANCE_MAPPING.csv`
- `CEP-035_EVIDENCE_MANIFEST.csv`
- `CEP-035_CHANGE_MANIFEST.csv`
- `CEP-035_COMPLETION_REPORT.md`

Evidence IDs must use `CEP-035-EV-001`, `CEP-035-EV-002`, ... and must not be fabricated during prompt generation.

## 23. Acceptance Criteria
Canonical acceptance criteria owned by this CEP; text and conditions are authoritative:

1. `IMB-0025` — 1) `Governed Price Book source/version engine` produces the approved target outcome: Official source/version/effective-date/provenance are first-class governed data.
   - Planned Verification: PLANNED: SERVICE
   - Planned Evidence: PLANNED: TEST OUTPUT
2. `IMB-0025` — 2) Valid lifecycle input persists only in the authoritative source: Owning domain remains authoritative..
   - Planned Verification: PLANNED: UNIT
   - Planned Evidence: PLANNED: TEST OUTPUT; CODE DIFF
3. `IMB-0025` — 3) Invalid or policy-absent input fails closed instead of inventing a default.
   - Planned Verification: PLANNED: UNIT
   - Planned Evidence: PLANNED: TEST OUTPUT; CODE DIFF
4. `IMB-0025` — 4) Correction/replacement preserves prior source identity/version where governed.
   - Planned Verification: PLANNED: SERVICE
   - Planned Evidence: PLANNED: TEST OUTPUT
5. `IMB-0025` — 5) Implementation stays within: Price Book model/import/version activation/provenance; fail closed without verified source.
   - Planned Verification: PLANNED: SERVICE
   - Planned Evidence: PLANNED: TEST OUTPUT
6. `IMB-0025` — 6) Excluded behavior remains absent: No official values invented; no silent replacement of historical versions.
   - Planned Verification: PLANNED: SERVICE
   - Planned Evidence: PLANNED: TEST OUTPUT
7. `IMB-0026` — 1) `Price Book mapping/version pinning` produces the approved target outcome: Mappings are versioned, immutable historically, explicitly remapped and source-traceable.
   - Planned Verification: PLANNED: MIGRATION; SERVICE
   - Planned Evidence: PLANNED: MIGRATION OUTPUT; DATA RECONCILIATION; TEST OUTPUT
8. `IMB-0026` — 2) Valid lifecycle input persists only in the authoritative source: Owning domain remains authoritative..
   - Planned Verification: PLANNED: UNIT
   - Planned Evidence: PLANNED: TEST OUTPUT; CODE DIFF
9. `IMB-0026` — 3) Invalid or policy-absent input fails closed instead of inventing a default.
   - Planned Verification: PLANNED: UNIT
   - Planned Evidence: PLANNED: TEST OUTPUT; CODE DIFF
10. `IMB-0026` — 4) Correction/replacement preserves prior source identity/version where governed.
   - Planned Verification: PLANNED: SERVICE
   - Planned Evidence: PLANNED: TEST OUTPUT
11. `IMB-0026` — 5) Implementation stays within: Mapping identity/version, effective date, remap/supersession, downstream revision linkage.
   - Planned Verification: PLANNED: SERVICE
   - Planned Evidence: PLANNED: TEST OUTPUT
12. `IMB-0026` — 6) Excluded behavior remains absent: No automatic remap when a new Price Book version appears.
   - Planned Verification: PLANNED: SERVICE
   - Planned Evidence: PLANNED: TEST OUTPUT
13. `IMB-0026` — 7) Any affected historical source records are preserved and before/after source-target reconciliation is produced.
   - Planned Verification: PLANNED: MIGRATION; SERVICE
   - Planned Evidence: PLANNED: MIGRATION OUTPUT; DATA RECONCILIATION

Acceptance criteria coverage for this CEP: `13 / 13`.

## 24. Definition of Done
- `IMB-0025` DoD: - Target outcome implemented for `Governed Price Book source/version engine` exactly within approved scope. - Approved lifecycle/capability implemented without hidden defaults. - Authoritative persistence/history implemented. - Invalid/policy-absent paths fail closed. - Domain/negative-path tests added.
- `IMB-0026` DoD: - Target outcome implemented for `Price Book mapping/version pinning` exactly within approved scope. - Approved lifecycle/capability implemented without hidden defaults. - Authoritative persistence/history implemented. - Invalid/policy-absent paths fail closed. - Domain/negative-path tests added. - Migration reconciliation and exception handling implemented for the affected historical references.

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
- `CEP-035_EXECUTION_MANIFEST.md`
- `CEP-035_ACCEPTANCE_MAPPING.csv`
- `CEP-035_EVIDENCE_MANIFEST.csv`
- `CEP-035_CHANGE_MANIFEST.csv`
- `CEP-035_COMPLETION_REPORT.md`

Evidence IDs must use `CEP-035-EV-001`, `CEP-035-EV-002`, ... and must not be fabricated during prompt generation.

The Completion Report must distinguish pre-existing failures, package-introduced failures, remaining UTV, blockers and downstream readiness.

## 30. Final Execution Verdict Format
At the end of this CEP execution/verification, report exactly one execution state:
- `EXECUTION COMPLETE`
- `EXECUTION PARTIAL`
- `EXECUTION FAILED`

Registry lifecycle/disposition fields such as `CLOSED_VERIFIED`, `BLOCKED`, `CANCELLED` or `SUPERSEDED` are recorded separately when applicable; they do not replace the execution state.

Required checkpoint fields:
- CEP ID: `CEP-035`
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
