# BONIRA — Wave C Blocker Decision Pack & Targeted Re-entry

## 1. Product Owner Decision Pack

### PD-WC-01 — Development specialist roles
APPROVE for Development / Non-Production only:

Codex may create the minimum tenant-scoped custom specialist roles required for Wave C, using only existing active `BusinessPermission` codes and the canonical `create_organization_role` / role-assignment / scope-grant services.

Constraints:
- no new permission codes;
- no change to permission semantics;
- no modification of built-in/system role defaults merely to make tests pass;
- least-privilege permission subset only;
- exact tenant/scope only;
- canonical dual-approval / audit controls remain enforced;
- no Platform privilege as a Tenant-data bypass;
- no Production authority.

This decision applies to bounded Development specialist roles such as Procurement Buyer, HR Administrator, Timekeeping Operator, Payroll Specialist, Document Specialist, Project Controls Analyst, Employment Manager / Employee Self-Service, and Supplier Portal Manager when required by the canonical Wave C scenario.

### PD-WC-02 — Procurement workflow
APPROVE:
- provision a bounded Procurement Buyer specialist role from existing permissions;
- remediate F-008 only by deriving stage, prerequisites, allowed actions and next action from the already-existing RFQ state/transition contract;
- do not invent a new procurement priority, approval rule, award rule, or business policy.

### PD-WC-03 — Payroll specialist boundary
APPROVE:
- do not reuse `p7_demo_payroll_assurance` as a Payroll-only persona;
- create a Development tenant-scoped Payroll Specialist role from the minimum existing Payroll permissions needed by RV-018;
- do not include unrelated sensitive Workforce permissions;
- do not activate or fabricate statutory rules.

### PD-WC-04 — Employment management
APPROVE bounded Product UI implementation:
- create the missing governed internal employment-record management surface using existing backend/domain services and existing `employment_records.*` permissions;
- provision least-privilege Development roles using existing permission codes;
- own-history access must use the explicit existing `Employee.user` relationship;
- never infer employee identity from username, name, email, national-id similarity or other heuristics;
- cross-tenant and non-own access must fail closed.

No new identity model is authorized.

### PD-WC-05 — External supplier portal
APPROVE:
- `supplier_portal.invitations_manage` may be explicitly assigned to a new tenant-scoped Development `Supplier Portal Manager` custom role;
- do not add this permission to built-in/default roles;
- external portal personas must remain external identities without Tenant membership unless the canonical design explicitly requires otherwise.

### PD-WC-06 — Existing policy/source activation
APPROVE only this bounded rule:

Codex may activate or provision an already-defined canonical Development policy/source configuration when:
1. its semantics and values are already fully determined by existing Product Decisions/specifications/code-owned defaults; and
2. no accounting, statutory, tender, recognition, tax, insurance, financial, or regulatory judgment needs to be invented.

If a required value/rule is not already canonically determined, STOP that scenario and report the exact unresolved field/rule. Do not fabricate financial/statutory/business policy.

This applies to RV-011, RV-013 and RV-030.

### PD-WC-07 — Document safety assessment
APPROVE:
- provision the minimum existing `Platform Operations` Development duty if required by the canonical processing-assessment service;
- use a genuine available Development scanner/processing mechanism against a benign synthetic document;
- do not fabricate a CLEAN assessment or bypass download safety;
- if no genuine scanner verdict can be produced in the available environment, retain only that exact external/environment blocker.

### PD-WC-08 — Scope of re-entry
Do not rerun already-closed Wave A/B, F111 family, SP031/F-128 or the already-PASS RV-009 except for necessary regression/smoke checks.

Re-enter only the blocked Wave C scenarios and their directly related open findings.

---

## 2. Codex Execution Prompt

### BONIRA Wave C — Blocker Resolution → Targeted Re-entry → Close

Repository:

`E:\Construction_Company_Solution`

Current canonical state:

- Wave C = `WAVE_C_BLOCKED`
- 12 canonical scenarios have explicit dispositions
- RV-009 Inventory = PASS
- F-129 and F-130 = `RUNTIME_VERIFIED_RESOLVED`
- F111 family / BATCH-01..09 = CLOSED
- SP031 / F-128 = RESOLVED
- accepted dirty working source is the effective baseline and must be preserved
- CEP-078/079 = NOT_EXECUTED
- Production = untouched
- no Git add/commit/push/merge

Primary evidence:

- `docs/governance/uiux/UIUX_RUNTIME_VALIDATION_WAVE_C_REPORT.md`
- `docs/governance/uiux/UIUX_RUNTIME_VALIDATION_RESULTS.yaml`
- `docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml`
- `docs/governance/uiux/wave_c_evidence/READINESS.json`
- `docs/governance/uiux/wave_c_evidence/POPULATED_STATEMENT.json`
- `docs/governance/uiux/wave_c_evidence/FIXTURES.json`
- `docs/governance/uiux/wave_c_evidence/DIRECT_SERVICE.json`
- `docs/governance/uiux/wave_c_evidence/VERIFICATION.json`
- `docs/governance/uiux/wave_c_evidence/INTEGRITY.json`

## Product Owner decisions authorized for this execution

Apply PD-WC-01 through PD-WC-08 from this prompt exactly.

### Authority

Development / Non-Production only.

You are authorized to:

- create minimum tenant-scoped custom specialist roles using only existing active `BusinessPermission` codes and canonical role services;
- provision minimum synthetic Development users, memberships, role assignments and explicit scopes;
- use canonical independent approval/audit controls;
- create bounded synthetic Development domain fixtures through canonical services;
- activate only already-determined canonical Development policy/source configurations under PD-WC-06;
- provision minimum existing Platform Operations duty only for genuine document-processing assessment;
- implement bounded UI/product remediation already authorized by these decisions;
- execute focused tests, regressions, authenticated HTTP, direct-service and genuine browser validation;
- update UI/UX finding/evidence records.

You are NOT authorized to:

- create a new permission code;
- weaken authorization or tenant isolation;
- turn Platform privilege into Tenant-data authority;
- change built-in/default roles merely to force PASS;
- invent accounting, tender, statutory, payroll, tax, insurance, recognition or regulatory rules;
- fabricate scanner/CLEAN evidence;
- infer Employee identity heuristically;
- perform Production actions;
- execute CEP-078/079;
- perform Git add/commit/push/merge.

## Required execution order

### 0. Re-ground
Verify repository/working-tree/effective baseline and preserve all accepted Wave C changes and evidence.

### 1. Resolve specialist-authority blockers first

For the blocked scenarios, inspect exact view/service permission requirements and create only the minimum tenant-scoped custom Development roles necessary from existing permissions.

Targets:

- RV-007 Procurement Buyer
- RV-015 HR Administrator
- RV-017 Timekeeping Operator
- RV-018 Payroll Specialist
- RV-028 Document Specialist
- RV-031 Project Controls Analyst
- RV-032 Supplier Portal Manager
- RV-029 Employment Manager / Employee Self-Service where applicable

Do not grant broad Owner/Admin roles merely because they contain the required permission.

Use explicit Project/Site/Organization scope appropriate to each scenario.

### 2. RV-007 Procurement
Provision the bounded Buyer authority.

Remediate F-008 using only the existing RFQ state machine and allowed transitions:
- show current stage;
- show completed/blocking prerequisites;
- make the uniquely valid next action primary when determinable from existing rules;
- subordinate exceptional/secondary actions.

If existing semantics do not determine a unique next action, do not invent priority; record the exact remaining ambiguity.

Execute positive A, same-tenant unauthorized, cross-tenant, site/object-scope and manipulated-action controls.

### 3. RV-015 HR
Use a least-privilege HR role constructed from existing permissions such as the exact capabilities required by the canonical surfaces.

Execute structure/foundation/create journeys plus sensitive-data and tenant/scope negatives.

No broad managerial-role substitution.

### 4. RV-017 Timekeeping
Use a least-privilege Timekeeping role from existing permissions.

Execute setup/calendar and daily-operation validation.

Remediate F-040 by separating setup/configuration from daily work through bounded UI organization only; do not change timekeeping business rules.

### 5. RV-018 Payroll
Create a Payroll Specialist custom role from existing Payroll permissions only.

Do not reuse `p7_demo_payroll_assurance` as the persona.

Execute run/statutory/handoff positive journeys to the maximum allowed by already-defined non-statutory/non-production rules.

Remediate bounded UI findings F-005/F-006/F-058/F-059/F-067/F-068/F-069 where the existing contract determines the presentation.

Any missing real statutory rule remains a precisely documented blocker; do not fabricate it.

### 6. RV-028 Documents
Create the minimum Document Specialist tenant role.

For safe download:
- use canonical processing-assessment service;
- if required, provision minimum Platform Operations Development duty;
- execute a genuine available scanner/processing path on a benign synthetic document.

Never synthesize a CLEAN verdict.

If the environment lacks a real usable scanner mechanism, record only that residual environment blocker after all other document validation is complete.

### 7. RV-029 Employment
Implement the missing governed internal employment-management UI using existing backend/domain services and existing permission codes.

Provision:
- Employment Manager role with existing `employment_records.manage`;
- bounded Employee Self-Service authority with existing `employment_records.view_own` if required.

Own-history identity must resolve only through explicit `Employee.user`.

Create minimum Development linked Employee/User fixture canonically if needed.

Validate:
- authorized management;
- own-history;
- unlinked user fail-closed;
- another employee denial;
- cross-tenant denial;
- manipulated identifiers;
- no sensitive metadata leakage.

No new identity model.

### 8. RV-030 Commercial
Provision the minimum specialist role using existing tender permissions.

Resolve the active Tender Policy only under PD-WC-06:
- if an already-defined canonical Development policy/version exists and its values require no new business judgment, activate it canonically and continue;
- otherwise stop this scenario with the exact missing policy decision/value.

Do not invent tender thresholds, scoring, approvals or award rules.

### 9. RV-031 Controls
Create the minimum Project Controls Analyst custom role from existing permissions, including only capabilities required by the canonical scenario.

Execute advanced comparison/exceptions/reconciliation with correct project/site/object scope and negative controls.

Do not invent Project Cost source facts.

### 10. RV-032 External Portal
Create a tenant-scoped Development `Supplier Portal Manager` role containing the existing `supplier_portal.invitations_manage` permission and only the other existing permissions strictly required by the invitation-management journey.

Do not modify built-in role defaults.

Create the canonical external identity/invitation/grant prerequisites without adding Tenant membership to the external identity unless the existing domain contract explicitly requires it.

Execute:
- invitation management;
- external acceptance;
- external grant;
- receipt/submission;
- tenant isolation;
- invalid/expired/manipulated token controls.

Remediate F-060 by computing integrity/idempotency metadata server-side from canonical submitted/uploaded payload where existing services already define the calculation. Do not weaken evidence integrity.

### 11. RV-011 Statements / RV-013 Settlement / remaining policy-source gates

Use PD-WC-06.

Attempt canonical Development activation only when all semantics are already determined by existing contracts.

RV-011:
- create populated statement data through canonical accounting services;
- no direct DB fabrication;
- no invented posting/accounting policy.

RV-013:
- create eligible obligation and posted Treasury source only through canonical services and already-defined recognition mappings;
- no fake cash movement or source recognition.

If either requires an undefined business/financial decision, capture the exact missing rule and leave only that scenario blocked.

### 12. Revalidate

For each remediated scenario run:
- focused automated tests;
- attributable regression;
- authenticated CSRF-bearing HTTP;
- direct-service positive/negative controls where applicable;
- genuine browser desktop/mobile validation;
- same-tenant unauthorized;
- cross-tenant;
- Project/Site/object scope;
- manipulated POST/identifier;
- invalid redisplay;
- metadata leakage;
- unauthorized mutation/audit checks;
- before/after integrity.

Preserve existing baseline debt separately from attributable failures.

Migration is expected `NO` unless the bounded Employment UI or other already-authorized remediation demonstrably requires an existing-contract schema migration. If a new schema/domain decision would be required, STOP that item instead.

### 13. Reconciliation

Update canonical Wave C evidence/results/findings.

Requirements for `WAVE_C_COMPLETE`:

- all 12 canonical scenarios have PASS;
- all Wave C bounded findings required for those scenarios are runtime-verified resolved;
- no unresolved specialist-authority fixture blocker;
- no invented policy/source/scanner evidence;
- no unauthorized authority or mutation;
- prior closed findings remain closed;
- Production/CEP-078/079/Git boundaries intact.

If a genuine residual blocker remains because a rule/value/source/scanner capability is not canonically determined or available, do not call Wave C complete.

Final status exactly one:

`WAVE_C_COMPLETE`

or

`WAVE_C_BLOCKED`

If blocked, report only the residual blockers that survived this authorized resolution pass, each with:
- scenario;
- exact missing decision/input/capability;
- why existing contracts cannot determine it;
- minimum Human/external input required.

Then STOP.
