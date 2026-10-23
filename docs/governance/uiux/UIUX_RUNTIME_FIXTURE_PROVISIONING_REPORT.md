# BONIRA UI/UX Runtime Persona & Fixture Provisioning

## Baseline

- Date: 2026-10-21 (Asia/Tehran).
- Branch: `main`; HEAD and `origin/main`: `43ac319c6e73e48ca9626461b73987922c498ec3`; local/upstream divergence: 0/0.
- Development DB: PostgreSQL `construction_erp`, `127.0.0.1:5432`, `config.settings.development`; 0 pending migrations at entry and closeout. No migrations executed.
- Governance: Checkpoint 15 documentation reconciliation COMPLETE; 26 personas / 33 scenarios retained.
- Historical status preserved: Wave A `WAVE_A_PARTIAL`; Wave B entry `WAVE_B_READY_WITH_EXPLICIT_BLOCKED_TARGETS`. Neither wave rerun.
- Existing untracked `docs/governance/uiux/` and `graphify-out/` preserved. All 111 pre-existing UIUX file hashes match entry; tracked source/index unchanged.
- Authority: the user's attached Development-only provisioning brief. No CEP execution or production authority inferred.

## Persona Provisioning

Persona is not Role. Results below distinguish a created identity from complete scenario coverage. A PARTIAL identity remains a persistent reference, with omitted capabilities explicit.

| Persona | Identity | Canonical role(s) | Scope | Result |
| --- | --- | --- | --- | --- |
| P-01 | uiux.audit.project | viewer | PRJ-01-01 | UNCHANGED |
| P-02 | uiux.persona.project-operations | member | PRJ-01-01, PRJ-01-02 | PARTIAL |
| P-03 | uiux.audit.project | viewer | PRJ-01-01 | NEEDS_PRODUCT_REVIEW |
| P-04 | not provisioned | none | none | NEEDS_PRODUCT_REVIEW |
| P-05 | account.demo-construction-01.accountant | accountant | organization | PROVISIONED |
| P-06 | uiux.persona.treasury | accountant | PRJ-01-01, PRJ-01-02 | PARTIAL |
| P-07 | uiux.audit.project | viewer | PRJ-01-01 | NEEDS_PRODUCT_REVIEW |
| P-08 | not provisioned | none | none | UNCHANGED |
| P-09 | not provisioned | none | none | UNCHANGED |
| P-10 | uiux.audit.project | viewer | PRJ-01-01 | UNCHANGED |
| P-11 | uiux.audit.project | viewer | PRJ-01-01 | UNCHANGED |
| P-12 | not provisioned | none | none | UNCHANGED |
| P-13 | not provisioned | none | none | UNCHANGED |
| P-14 | uiux.audit.reporting | none | none | UNCHANGED |
| P-15 | account.demo-construction-01.owner | tenant_owner, p7_demo_payroll_assurance | organization | PROVISIONED |
| P-16 | uiux.persona.tenant-admin | tenant_admin | organization | PROVISIONED |
| P-17 | uiux.persona.project-manager | project_manager | PRJ-01-01, PRJ-01-02 | PARTIAL |
| P-18 | admin | platform_admin (platform), tenant_owner | demo-construction-01:organization, demo-construction-02:organization, demo-construction-03:organization, demo-construction-04:organization | UNCHANGED |
| P-19 | uiux.audit.project | viewer | PRJ-01-01 | UNCHANGED |
| P-20 | not provisioned | none | none | UNCHANGED |
| P-21 | not provisioned | none | none | UNCHANGED |
| P-22 | uiux.audit.project | viewer | PRJ-01-01 | UNCHANGED |
| P-23 | uiux.audit.project | viewer | PRJ-01-01 | UNCHANGED |
| P-24 | uiux.audit.project | viewer | PRJ-01-01 | NEEDS_PRODUCT_REVIEW |
| P-25 | uiux.audit.project | viewer | PRJ-01-01 | UNCHANGED |
| P-26 | not provisioned | none | none | UNCHANGED |

Priority decisions:

- P-02: `EXISTING_CANONICAL_ROLE` (`member`), A/B scopes. Daily-report/request creation ready; estimate/expense/equipment-assignment creation remains outside that role.
- P-03, P-04, P-07, P-24: `MISSING_PRODUCT_ROLE` / `AUTHORIZATION_MODEL_GAP` for a suitably bounded specialist. Existing permissions are present in broader roles, but those bundles were not assigned merely to satisfy personas. Existing read aliases remain unchanged. No new specialist identities created for these gaps.
- P-05: retained accountant account corrected through `revoke_membership_role` → `assign_membership_role(accountant)` → `grant_membership_scope(organization)`. The prior canonical `tenant_manager` assignment remains as revoked history. Permission union reduced 402 → 167; previously there was no usable scope. Legacy compatibility role fields remain intact. Organization financial scope is required by the current `create_journal` service; this is a canonical Accountant, not an organization-wide manager.
- P-06: existing `accountant` role includes Treasury capability. Dedicated A/B-scoped identity prepared, but `MISSING_SCOPE` remains at organization-context Treasury entry/account-management gates. No organization grant added merely to simplify testing.
- P-15: existing `tenant_owner` and `p7_demo_payroll_assurance` mapping retained exactly; credential recovery only.
- P-16: `IDENTITY_ONLY_GAP` resolved using existing canonical `tenant_admin`; separate identity, tenant scope, no Owner/platform/staff/superuser assignment. Current canonical role bundle is recorded without redesign.
- P-17: existing canonical `project_manager`, explicit A/B grants, C and Tenant B denied. Operational authority prepared; `project_controls.compare` and `project_controls.exceptions_view` remain absent, so advanced managerial comparison is not claimed ready.
- Other personas: unchanged, including P-21 product/UI gap and P-26 missing portal principal/invitation/grant.

Canonical authorization assigner: `account.demo-construction-01.owner`. Independent authorization co-approver: the existing `admin` **tenant_owner membership** in `demo-construction-01`. The assignment services evaluate this tenant membership; platform authority supplies no override. Neither account performed domain fixture operations as a specialist. Domain fixture actors were the actual Member, Project Manager, and Accountant accounts.

## Credential Recovery

| Username | Result |
| --- | --- |
| account.demo-construction-01.owner | CONTROLLED_CREDENTIAL_RESET |
| account.demo-construction-01.supervisor | CONTROLLED_CREDENTIAL_RESET |
| account.demo-construction-01.accountant | CONTROLLED_CREDENTIAL_RESET |
| uiux.audit.project / uiux.audit.empty / uiux.audit.reporting | NOT_REQUIRED |
| admin and other retained aliases | NOT_REQUIRED |

Same accounts retained. Each reset used `reset_organization_member_password` and `initialize_personal_password`; per-reset pre/post authorization fingerprints matched. The accountant's separately approved role correction occurred before its credential-only reset. All seven prepared/recovered account credentials were checked in memory; first-login initialization is complete.

Passwords exist only in the existing Windows current-user DPAPI PSCredential store under `%LOCALAPPDATA%/BONIRA/UIUXRuntimeAudit/credentials/`, outside the repository. No login/browser runtime was executed. New-account initial credentials are in that same store. No credential values appear in this report or registry.

## Test Fixture Provisioning

| Scenario | Fixture | Created/Reused | Canonical path | Status |
| --- | --- | --- | --- | --- |
| RV-023 | 30 P-01-authorized daily reports in Project A; page size 25, expected 25/5 | 9 reused + 21 created | `daily_reports.services.create_daily_report`; existing scoped selector; paginator data-shape assertion | FIXTURE_READY; runtime pagination not rerun |
| RV-024 | Reporting identity and role retained; no closeout case | Reused; failed assignment rolled back | `organizations.access_services.assign_membership_role` | BLOCKED_AUTHORIZATION_FIXTURE |
| RV-033 | P-16 future viewer assignment; member assignment created then revoked | Created | `assign_membership_role` / `revoke_membership_role` | HISTORY_FIXTURES_READY; no runtime PASS |
| RV-006 | A/B projects, sites/phases; two reference estimates; two draft expenses; daily reports; A/B active equipment deployments | Reused + 2 estimates, 2 expenses, 1 deployment created | `create_estimate`, `create_expense_draft`, `create_daily_report`, `assign_equipment` | P-17 operational fixture/authority subset ready; P-02/P-24 gaps retained |
| RV-008 | Approved A/B requests, each with 2 items; eligible active supplier; C/cross-tenant approved requests | Reused | Existing canonical Development seed; checked current approved state, items, supplier role; canonical PO service reviewed | P-17 data/authority subset ready; P-03 blocked; PO not created |
| RV-010 | FY-1405; open period 3; posting accounts 5100/2100; draft manual journal with 2 balanced lines across A/B and actual site/WBS dimensions | Fiscal/account/context reused; journal + 2 lines created | `accounting.services.create_journal` / `add_journal_line` | FIXTURE_READY; no submission/posting |
| RV-012 | Reference cash account with explicit P-06 custodian | 1 created, draft | `treasury.services.create_treasury_account` | PARTIAL; active account, eligible approved source and movements blocked |
| RV-014 | Approved A baseline and verified progress | Reused; claim attempt rolled back | `billing.services.create_progress_claim` | BLOCKED: no approved contract-term version for cutoff; certificate/statutory specialist gap also remains |
| RV-019 | Asset and A deployment; reference meter, finalized reading, usage, preventive plan and draft work order; B deployment | Reused + 5 operational records and 1 B deployment created | `EquipmentMeter.full_clean/save` with canonical permission/audit; `p8_services.record_meter_reading`, `record_usage`, `create_maintenance_plan`, `create_work_order`; `assign_equipment` | PARTIAL: Project Manager data prepared; P-04 role, qualification and cost-policy/rate gaps retained |

Expense route for later validation: `/expenses/create/`. The historical matrix's `/expenses/new/` was not used or rewritten.

RV-033 scheduled assignment is bounded to 2099-01-01 through 2099-01-08 UTC, currently ineffective. Its viewer permissions are a subset of the already-active Tenant Admin role. Revoked member history retains assigning/approving/revoking actors and reason. No account is deactivated.

No equipment meter-creation service exists. The fixture used the current validated `EquipmentMeter` model path after checking the Project Manager's permission and A deployment scope, and appended the existing equipment-operation audit action. It made no authorization-table write.

## Boundary Fixtures

| Boundary | Authorized | Unauthorized same tenant | Unauthorized cross tenant |
| --- | --- | --- | --- |
| P-02 / P-17 / scoped financial P-06 | PRJ-01-01 (A), PRJ-01-02 (B) | PRJ-01-03 (C), also no grant to PRJ-01-04 | demo-construction-02 / PRJ-02-01 |
| Existing P-01 | A | B/C | demo-construction-02 / PRJ-02-01 |
| Procurement | Approved A/B requests with 2 items | Approved C request | Approved Tenant B request |
| Accounting | A/B site/WBS dimensions in new draft journal | C dimensions retained for scoped P-06 comparator | Tenant B project/site/WBS retained |
| Equipment deployment | A asset/deployment for P-01; A/B for P-17 | New B crane deployment is outside P-01 scope; no P-17 C deployment exists | Existing Tenant B equipment/deployment |

All scoped positive/negative project shapes were checked using canonical `membership_has_scope`. No cross-tenant grant was created. P-05 has organization financial scope, so C is legitimately visible to P-05; it must not be misreported as an out-of-scope P-05 project. P-06 supplies scoped financial authority but currently fails the organization-context Accounting/Treasury entry gate. No full end-to-end scoped Accountant scenario is claimed.

Object IDs and canonical source paths are in [the fixture registry](UIUX_RUNTIME_FIXTURE_REGISTRY.yaml) and evidence. Browser/form selection, manipulated request rejection and UX behavior remain for a separately authorized runtime session.

## Authorization Integrity

DIRECT_AUTH_DB_WRITE: NO  
NEW_PERMISSION_CREATED: NO  
ARTIFICIAL_SUPER_ROLE_CREATED: NO  
OWNER_USED_AS_SPECIALIST: NO  
PLATFORM_ADMIN_USED_AS_BUSINESS_ACTOR: NO  
CROSS_TENANT_SCOPE_CREATED: NO

All memberships, role/scope assignments, revocation, quarantine completion and credential changes used the existing canonical services. Role definitions, permission catalog and role-permission links are byte-for-byte fingerprint-equivalent. The existing `admin` account served only as tenant authorization co-approver, never as a domain fixture actor or platform bypass.

Authorization fingerprints:

- Before: `89beb3e15e6a0340fced57485ad31073558c6252d9dd82a37f32a370beb5d01e`
- After: `dc41830339a943bd6aab2820da7340fc3e7d361f2e3643cae153b5abf3393007`

The difference is attributable solely to the four new approved persona memberships and the retained accountant correction. Every other existing identity's authorization snapshot matches. Business fixture preparation left the post-provisioning authorization fingerprint unchanged.

## Product / Authorization Gaps

- P-03, P-04, P-07 and P-24: bounded specialist role coverage missing; permissions found only in unsuitable broad bundles. NEEDS_PRODUCT_REVIEW / AUTHORIZATION_MODEL_GAP; no role invented.
- P-02: canonical Member supports a useful operational subset, not all RV-006 creation surfaces.
- P-06: project grants do not satisfy current organization-context Treasury entry, source-picker visibility or account management. No scope broadening or authorization redesign performed.
- P-17: operational Project Manager authority exists; advanced comparison/exception permissions do not. No extra role added.
- P-21 and P-26: previous product/UI and portal-authorization gaps unchanged; not provisioned by this task.

## Ready Runtime Targets

These are fixture/identity prerequisites cleared for a later session, not runtime PASS or a wave-entry recertification:

- RV-023 / P-01 pagination: exact 30 authorized rows, expected pages 25/5.
- P-15 Owner comparison targets in RV-002/004/005/026: retained authority plus usable recovered credential.
- Supervisor credential-dependent no-workspace target: usable recovered credential; unchanged zero-scope/quarantined authorization.
- RV-004/026 / P-16 administration comparison and RV-033 P-16 authority/history subtargets: canonical Tenant Admin identity and traceable histories prepared.
- RV-006 / P-17 operational create/cascade subset: A/B contexts plus representative module records and relevant canonical create permissions.
- RV-008 / P-17 approved-request-to-PO preparation subset: approved requests/items/supplier/context plus canonical PO-create authority. Actual form/workflow behavior unexecuted.
- RV-010 / P-05 journal form/dimension fixture: valid canonical Accountant, open period, posting accounts and dimension-bearing draft.

RV-019 has additional reusable operational data, but P-04 specialist readiness is not established. No blocked specialist is substituted by P-17 or P-16 for scenario validation.

## Remaining Blockers

1. RV-024 Reporting: canonical assignment denied because assigner lacks `accounting_recognition.view`, `reporting.metric_result.view`, `reporting.project_closeout_case.prepare`, `reporting.project_closeout_case.view`, `reporting.reconciliation_run.view`. Reporting remains quarantined with zero roles/scopes. No lawful assigning actor in this tenant currently holds these permissions; no transfer bypass attempted. Closeout remains blocked at the same authority boundary; profile/case prerequisites were not manufactured.
2. RV-012: no active Treasury account, effective approved account-to-GL mapping, independent scoped-finance checker, approved employee-reimbursement source, or movement lifecycle. Zero governing budget controls and approved reimbursement expenses exist. Current movement picker accepts approved employee-reimbursement sources only. No budget acceptance, mappings or financial-policy semantics invented to force this flow.
3. RV-014: canonical claim creation rejected absent approved contract terms for the measurement cutoff. No claim/measurement/certificate/guarantee/compliance/statutory/invoice/submission lifecycle manufactured. Existing approved baseline and verified progress remain reusable. No statutory activation.
4. RV-019: no bounded P-04 role, approved operator qualification link or approved equipment cost policy/rate/allocation fixture. No inferred workforce identity or cost authority.
5. P-02 full cascade capability, P-17 advanced comparison, P-03/P-07/P-24 specialist coverage remain explicit gaps.
6. Existing runtime error/unauthorized-Home natural-state gaps, P-21 and P-26 remain unchanged. No fault injection or unrelated provisioning performed.

## Verification and Mutation Evidence

- Focused fixture integrity: **42/42 PASS**. Django system check: **0 issues**. Pending Development migrations: **0**.
- 514 model snapshots; exactly 20 planned model surfaces changed, 494 unchanged. No posted journal, Treasury movement, approved/finalized source-history mutation, new policy, role definition or permission created.
- 4 users, 4 memberships, 7 role-assignment rows, 8 scope rows added. Accountant's old assignment revoked; four new-account migration issues canonically resolved. No quarantine field edited directly.
- Business rows added: 21 daily reports, 2 estimates/revisions, 2 draft expenses, 1 draft journal/2 dimension-bearing lines, 1 draft Treasury account, 1 active equipment deployment, 1 meter, 1 reading, 1 usage, 1 maintenance plan and 1 draft work order. Existing crane status changed through `assign_equipment` only. 64 append-only audit events added.
- No broad test suite, browser interactions or Wave A/B runtime scenarios were run. Checks cover fixture shape, current effective authority, credential usability and mutation integrity only.

Evidence: [before](runtime_evidence/fixture_provisioning/BEFORE.json), [mutation plan](runtime_evidence/fixture_provisioning/MUTATION_PLAN.json), [identity changes](runtime_evidence/fixture_provisioning/IDENTITY_RESULT.json), [after](runtime_evidence/fixture_provisioning/AFTER.json), [verification](runtime_evidence/fixture_provisioning/VERIFICATION.json). The registry references per-scenario fixture outcomes and durable object IDs.

Preparation input recovery: the first credential-store call failed before DB mutation due to Windows PowerShell module loading; installed PowerShell 7 succeeded. Manual-journal opening-only cutoff, missing cash custodian and excess usage decimal precision were rejected and rolled back, then corrected within canonical input contracts. The equipment helper's missing required message argument failed before mutation. Original failed-attempt evidence is retained; no product patch or constraint weakening occurred. The Billing contract-term blocker remains unresolved. Local preparation scripts are outside the repository and are not an authorized automatic rerun mechanism.

Retain all persistent identities and clearly marked Development fixtures for reuse. No cleanup/deactivation/deletion is implied. Reverify permissions, scope and state before later runtime use; subsequent operations require their own authorized session.

## Safety Boundary

PRODUCT UI REMEDIATED: NO  
AUTHORIZATION SEMANTICS CHANGED: NO  
PRODUCTION ACTION: NO  
CEP-078 EXECUTED: NO  
CEP-079 EXECUTED: NO  
GIT WRITE: NO

CEP registry, Roadmap, historical Wave A/B evidence, canonical persona catalogue and findings were not rewritten. This report and fixture registry describe the current preparation delta only.

## Final Decision

RUNTIME_FIXTURE_LAYER_READY_WITH_EXPLICIT_GAPS
