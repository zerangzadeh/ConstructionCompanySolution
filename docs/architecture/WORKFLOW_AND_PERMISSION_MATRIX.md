# Workflow and Permission Matrix

**Status:** cross-domain policy reference; exact current transitions and grants remain code/test authoritative

**Workflow architecture:** `TENANT_WORKFLOW_AND_WORK_MANAGEMENT.md`

**User goals:** `USER_CAPABILITY_MAP.md`

## 1. Purpose

This document keeps lifecycle, permission, responsibility and separation rules
visible across domains. It prevents three common errors:

1. treating a role, position, UI control or workflow assignment as sufficient authorization;
2. allowing the workflow engine to mutate domain state generically; and
3. creating a new approval/task mechanism inside each domain.

## 2. Authorization equation

An action is permitted only when all applicable conditions pass:

```text
authenticated and effective User
+ active OrganizationMembership
+ all active independent role assignments for that Membership [target]
+ active/non-blocking Organization state
+ entitled capability/quota [target]
+ required BusinessPermission resulting from all applicable assigned roles
+ project/site/object scope [target]
+ valid domain state and required data
+ current WorkItem assignment/candidacy/delegation [workflow action]
+ separation-of-duties and effective-position evidence [when configured]
= authorized domain service command
```

The domain service re-reads and re-authorizes inside the transaction. UI
visibility, possession of an ID, `Employee`, `Position`, department/team,
candidate membership or Superuser convenience is not ordinary business authority.

## 3. Permission ownership

- `BusinessPermissionCode` and `permission_registry` define application
  capabilities; default-role grants are data-migrated and tested.
- Each `OrganizationRole` maps to a permission set. Current protected role codes
  remain code-authoritative until the approved canonical role migration.
- Tenant/business roles are assigned to `OrganizationMembership`, not globally to
  `User`. One User may therefore hold a different independent role set in each
  Tenant. The target relationship is conceptually
  `User -> Membership -> MembershipRoleAssignment -> Role` (or an equivalent
  Tenant-preserving model).
- A Membership may hold multiple roles simultaneously. Effective role-derived
  permissions are the union of permissions from all active applicable role
  assignments, then remain intersected with every other factor in the authorization
  equation. Role union never creates project/site scope, delegation, workflow
  eligibility or a policy exception.
- Do not create composite roles merely because assignments commonly co-occur.
  Assigning or revoking Tenant Owner, Tenant Admin, Tenant Manager, Project Manager
  or another role affects only that assignment and never implicitly changes another.
  Assignment and revocation evidence retains actor, Tenant, role, timestamp and
  relevant reason/context.
- Platform roles are **Superuser** and **Platform Admin**. Superuser is the highest
  exceptional technical/system authority; Platform Admin is the operational
  platform-administration role. They are independent, may be explicitly co-assigned to
  one user, and neither implies the other. Neither role alone grants Tenant
  business-data access.
- Tenant roles are **Tenant Owner**, **Tenant Admin** (also called **Local Admin**)
  and **Tenant Manager**, plus domain profiles such as Accountant, Supervisor and
  Viewer. Tenant Owner owns high-level Tenant policy; Tenant Admin operates Tenant
  administration within delegated boundaries; Tenant Manager owns business/
  operational management. These roles are independent, may be explicitly
  co-assigned, and do not inherit one another implicitly.
- Current protected role codes remain code-authoritative until an approved role
  migration. The implemented membership currently references one role definition;
  multi-role Membership assignments are target documentation, not implementation.
- Project/site grants can only restrict/intersect tenant permission. They do not
  create a second permission catalogue.
- Workflow position routing records who was responsible. It never grants the
  underlying business permission.
- Every sensitive export, archive, void, reversal, close/reopen, support access,
  payroll/financial view and approval may require a distinct permission.

## 4. Typical target default-role policy

This matrix guides future default grants; it does not override the current role
catalogue or eliminate per-capability/SoD design.

| Capability family | Tenant Owner | Tenant Admin / Local Admin | Tenant Manager | Accountant | Supervisor | Viewer |
| --- | --- | --- | --- | --- | --- | --- |
| Tenant lifecycle/ownership/plan/export | Govern | Configure limited | No default | No default | No default | Read own context |
| Membership/role/object scope | Govern/protect Tenant Owner | Administer delegated grants | Scoped business delegation only | No default | No default | No |
| Shared masters | Govern | Manage | Manage scoped | Read/use; sensitive party/bank as granted | Read/use scoped | Read scoped |
| Projects/operations | Govern | Configure | Manage/approve scoped | Read financial context | Record/review assigned site | Read scoped |
| Contracts/claims/procurement | Govern exceptional | Configure | Manage/approve configured | Financial review/posting, not automatic technical approval | Request/record assigned operations | Read scoped |
| Accounting/Treasury/Payroll | Oversight, not automatic maker+checker | No default sensitive approval | Budget/commercial approval only as configured | Prepare/review/post/reconcile with SoD | Time/site inputs only | Highly restricted read |
| HSE/Quality | Oversight | Configure | Manage scoped | Read cost/compliance as granted | Report/inspect/act assigned | Read scoped/sensitive limits |
| Workflow administration | Publish only with dedicated permission | Configure delegated | Domain policy as granted | Financial workflow as granted | Act on assigned items | No action |
| Audit/export/support access | Oversight with dedicated permission | Operational limited | Scoped evidence | Financial evidence | Own/scoped evidence | Read only if granted |

Tenant Owner status alone supplies no Tenant Admin privilege, bypass or
Self-Approval authority. Under the
[final G3 — Revised with Protected Operations decision](P0_S14_Q04_PRODUCT_OWNER_DECISION_PACKET.md#q04-g-maker-checker-separation-and-small-tenant-fallback),
Protected Operations prohibit Self-Approval; non-protected business operations may
be made configurable by platform policy and enabled by an authorized tenant actor
where permitted. Every policy change and use requires audit; reviewer evidence and
implementation remain open.

## 5. Delivered lifecycle matrix

Exact service names/statuses may evolve; consult models/services/tests before
implementation work.

| Domain aggregate | Delivered lifecycle/action | Required authority pattern | Finality/correction |
| --- | --- | --- | --- |
| Organization | active/suspend/cancel/archive and settings/membership operations | Platform Admin/control-plane or dedicated Tenant-governance permission; Tenant Owner protection | Lifecycle and export/retention evidence audited |
| Membership/role | provision/connect, independently assign/revoke roles, suspend/revoke membership | Membership-management permission; cannot grant capabilities actor lacks; changing one assignment changes no other | Actor/Tenant/role/time/reason history; final active Tenant Owner assignment protected |
| Project/phase/activity | create/update/transition/archive | Domain permission + tenant/project hierarchy | Completed/cancelled/archive restrictions; no cross-tenant hierarchy |
| Contract | draft -> active/completed/terminated | Contract view/manage/transition permission | Non-draft terms immutable; change through amendment |
| Contract amendment | draft -> approved | Amendment approval permission and valid contract context | Approved amendment immutable |
| Estimate/revision | draft/revise -> approve/supersede | Estimate permissions plus workflow candidacy where adopted | Approved/superseded revision retained |
| Daily report | draft -> submitted -> approved | Report permission plus assigned workflow responsibility | Submitted/approved content locked; correction is explicit |
| Purchase request | draft -> submitted -> approved/rejected/cancelled | Procurement permission plus shared workflow candidate/assignment | Decision/audit retained; compatibility policy preserved |
| Purchase order | draft -> issued -> completed/cancelled | Order permission and quantity/context rules | Issued/received history protected |
| Goods receipt | draft -> posted -> void | Receipt permission; stock-link constraints | Void preserves evidence and handles linked stock movement |
| Stock transaction | draft -> posted -> reversed | Inventory post/reverse permission; warehouse/project scope | Reversal creates equal-and-opposite posted movement |
| Equipment assignment | scheduled -> active -> completed/cancelled | Equipment permission; non-overlap and site/project rules | Terminal history retained |
| Maintenance | scheduled -> in-progress -> completed/cancelled | Maintenance permission and workflow where actionable | Completed/cancelled immutable |
| Expense | legacy recorded -> void; new draft -> submitted -> approved/returned -> void | Dedicated view/create/allocate/submit/approve/return/void/recurrence permissions; maker/submitting actor cannot approve; project scope | Source and coded split evidence retained; exact conservation; approval has no AP/GL/Treasury side effect; reasoned void |
| Payment/allocation | posted -> void; allocation active -> reversed | Payment/allocation/void/reverse permission | Cash evidence and allocation reversals retained |
| Document/version/link | add version/link, archive, view/download | Document permission plus view access to every linked context | Version instance guards and archival; links retained by services/Django Admin, with a model update gap recorded in [S09](ADR_P0_S09_DMS_DOMAIN_LINKS.md#1-verified-current-link-contract) |
| Safety incident | report -> review -> assign -> corrective action -> resolve -> close | HSE permission + work-item responsibility + responsible-party checks | Closed immutable; audit/reopen only if separately designed |
| Quality issue | report -> review -> assign -> corrective action -> verify -> close | QA permission + work-item responsibility; verifier evidence | Closed immutable; verification/closure evidence retained |
| Baseline | draft -> approved/superseded | Baseline permission + workflow assignment/candidacy | Approved baseline immutable |
| Progress record | draft -> submitted -> verified/rejected/corrected | Record/verify permission + distinct work item | Verified source immutable; correction links replacement |
| Progress claim | draft -> submitted -> approved/returned revision | Claim permission + eligible approver/candidacy + separation | Submitted snapshot frozen; approved/returned revision immutable |
| Claim settlement | allocate -> reverse | Settlement permission; approved claim and compatible payment allocation | Append/reverse; never synthesizes cash |
| Workflow definition/version | draft configuration -> publish | Dedicated workflow-administration/publish permission | Published version immutable |
| Work item | offer/claim/release/act/reassign/delegate/complete | Underlying domain permission + candidacy/assignment + separation | Assignment/decision history append-only |
| Accounting reconciliation | retain -> disposition -> sign off | Dedicated run/disposition/sign-off permissions; signer differs from run creator and every disposer | Runs, exceptions, tie-outs, dispositions, reviews and audit are append-only; sign-off changes no journal or balance |

## 6. Target workflow matrix

| Roadmap capability | Principal states/decisions to design | Permission/SoD requirements | Roadmap |
| --- | --- | --- | --- |
| Tenant plans/offboarding | entitlement change, grace/suspend/cancel, export/hold/delete decision | Tenant Owner/Platform Admin split; protected Superuser operations remain separate; export and destructive retention separate; no support bypass | P0.3 |
| Object-scope grants | propose/grant/change/revoke/emergency access | Cannot self-elevate; grantor must hold delegated authority; full audit | P1.1 |
| Regulatory rules | draft/review/activate/supersede | Legal/accounting reviewer; maker cannot be sole activator where required | P1.2 |
| Material/technical approval | draft/review/approve/reject/archive/substitute | Master-data vs technical/quality approval separation | P1.4 |
| Journal/period close | propose/review/post/reverse/replace/adjust; open/close/reopen | Maker-checker; close requires no pending accounting artifacts, cutoff-matched signed reconciliation and retained statements; reopen is separately permissioned and independent from the close approver; late adjustment is a new linked journal in an explicit open adjustment period | P2 |
| Treasury/AP/AR | propose/approve/release/clear/reconcile/review/write-off | Treasury S05–S22 enforces its dedicated permissions and lifecycle. AP/AR S23–S27 adds dedicated view/recognize/allocate/reverse/aging/reconciliation/proposal permissions, exact Tenant/object scope, immutable evidence and concurrent caps. S30–S31 adds separately permissioned immutable cash-to-GL and AP/AR reconciliation review with direct maker-checker enforcement. Source/posting adapters fail closed; write-off approval/reversal have no default grant and remain disabled until authority/SoD is approved. P3-S32 records handoff only: no Treasury/AP/AR fact becomes a Project Cost fact without a separately authorized classified source contract. | P3-S05–S31 implemented; P3-S32 closeout complete; P3-S28–S29 acceptance and activation gates open |
| Estimate/BOQ/budget/project cost and controls | import/validate/revise/compare/approve/handoff/submit/accept; approve producer contract; record immutable projection; reconcile bounded evidence; prepare schedule/register/change/rebaseline evidence | P4-S07–S37 uses dedicated permissions, exact Tenant/project scope, immutable accepted budget/cost history, coded conservation and deterministic locks, cycle-safe draft schedule dependencies, append-only register/change/rebaseline evidence, and separately permissioned/audited read-only comparison, exception, export and incomplete multi-source reconciliation evidence. Baseline/change/rebaseline approval permissions have no default grant and their services fail closed; Project Controls cannot establish source authority, contractual entitlement or mutate financial/source facts. | P4-S01–S37 safe authorized scope implemented; P4-S38, forecast/schedule/change/rebaseline acceptance, scoring, integrations, EV and producer activation gated |
| Expense | draft/submit/approve/return/void/allocate; propose recurrence | P4-S26–S30 enforces requester/submitter vs approver, Tenant/project scope, duplicates/idempotency and conserved accepted-budget coding; finance settlement remains distinct | P4-S26–S30 implemented safe scope; P4-G10 enforcement policy and downstream settlement/posting remain gated |
| RFQ/quote/award/invoice match | issue/invite/submit/open/compare/award/receive/match/exception | Bid confidentiality; requester/buyer/award/receipt/AP separation | P5.1 |
| External portal | invite/accept/submit/revise/withdraw/internal accept/reject | External party/object scope; no internal notes/competitor data; internal finalization | P5.2 |
| Contract/payable claim/guarantee | terms/variation/certificate/retention/release/expiry/clearance | Commercial/technical/finance approval limits and evidence | P6 |
| Taxpayer/contractor compliance | preflight/submit/accept/error/correct/cancel/clear | Credential isolation, legal reviewer, correction chain and retry ownership | P6.3 |
| Qualification/training | evidence/review/approve/expire/revoke/evaluate | Personal-data scope; evaluator conflicts; qualification not permission | P7.0 |
| Time/payroll/insurance | enter/import/review/approve/finalize/adjust/reverse/submit/pay | Supervisor/HR/payroll/accounting/Treasury separation; run/period lock | P7.1/P7.2 |
| Inventory valuation/count/transfer | reserve/release, count/freeze/approve, dispatch/accept, value/reverse | Warehouse/project scope; counterparty custody; count variance approval | P8.1 |
| Equipment/asset | usage/fuel/maintenance approval; capitalize/depreciate/impair/dispose | Operations vs asset/accounting approval; source reconciliation | P8.2 |
| Field/document control | draft/capture/review/issue/respond/approve/supersede/transmit | Project/external scope; reviewer independence; immutable issue/version | P9.1/P1.3 |
| HSE/QA | inspect/report/investigate/assign/CAPA/verify/close/escalate | Reporter/assignee/verifier separation; sensitive access; due escalation | P9.2 |
| Partner qualification/performance | submit/review/approve/evaluate/appeal/expire/block | Evidence/reviewer conflict; explainable score and category/time scope | P9.3 |
| Support/access | open/triage/respond/escalate/resolve/reopen; grant/expire/revoke | Tenant-approved timed support access; diagnostics consent; SLA audit | P9.4 |
| Knowledge | author/review/publish/revise/retract/promote/review expiry | Source citation; reviewer/publisher; AI cannot publish | P9.5 |
| Reconciliation/close | generate/assign/investigate/resolve/reopen/accept close | Control owner distinct from source maker where material | P10.2 |

## 7. Separation-of-duties and Self-Approval baseline

The Product Owner selected final **G3 — Revised with Protected Operations** instead
of the original G1 recommendation and replaced every earlier Q04-G response.
Platform-level `Protected
Operations` mandate separation for system, security, authorization, privileged-
access and access-management operations where Self-Approval could elevate the
actor or bypass a security control. Self-Approval is never allowed for these
operations. Tenant configuration and Tenant Owner, Tenant Admin, Platform Admin
or Superuser roles cannot override this prohibition.

At minimum, Protected Operations cover self-grant/access increase, own privileged-
role assignment/approval, own support/emergency access, same-actor change and
approval of authorization/security policy, same-actor weakening and approval of
audit/security controls, and equivalent system-level self-elevation or control
bypass.

Other functional/business operations—including financial, contractual, project,
procurement, administrative and workflow approvals—may support configurable
Self-Approval. Superuser defines at platform level which business operation types
support it. Where permitted, a Tenant Owner or another Tenant user with the
explicit policy-management permission may enable or disable it according to that
Tenant's policy. Tenant Owner status alone enables nothing. Changing the platform
classification is a Protected Operation because it
changes authorization policy; Platform Admin assignment alone does not supply the
Superuser capability. There is no special single-user-tenant mode or classification.

Each package still identifies the following operation combinations so they can be
configured, reviewed, displayed and audited explicitly:

- creating and approving the same procurement, expense, claim or journal;
- preparing and releasing the same payment/cheque/transfer;
- recording and verifying the same progress/inspection/test;
- calculating and finalizing the same payroll run;
- administering a rule/workflow and approving a transaction affected by it;
- granting one's own role/scope/elevation or support access;
- reporting/investigating/closing the same HSE/QA case; and
- creating and resolving the same reconciliation exception.

Every policy/configuration change records actor, date/time, Tenant where applicable,
operation, previous/new values and required reason/context; every actual
Self-Approval use is also audited. Self-Approval never supplies a missing membership,
permission, object scope, delegation or valid domain state. Configuring it for
financial, contractual, statutory or independent-verification business actions
carries heightened fraud, error-detection, professional-validity and regulatory
risk. Tenant enablement remains subject to its internal-control, contractual,
accounting, audit, legal and regulatory obligations. Required named reviewers must
assess classification completeness, those risks and release implications.

## 8. Project/site and external scope

The [S07 scope ADR proposal](ADR_P0_S07_PROJECT_SITE_AUTHORIZATION.md) records
current selector/runtime differences and proposed grant/workflow semantics.
It is not an accepted ADR or P1.1 implementation. Q04-A through Q04-H Product Owner
selections are recorded, but accountable reviewer names/evidence remain OPEN; the
target bullets below grant no runtime access.

The [S11 lifecycle/support ADR proposal](ADR_P0_S11_TENANT_LIFECYCLE_ENTITLEMENTS_SUPPORT.md)
adds entitlement/capacity, inactive-tenant export and offboarding boundaries.
It preserves current active-tenant checks and implements no support, Tenant Owner,
privileged or background exception. Revised F2 and E1 supply policy direction;
D03-D05/Q03 and accountable Q04 review remain open, and P0.3 is not implemented.

- Tenant permission is necessary but may be narrowed by project/site scope.
- Parent/child relationships are validated server-side; filtering a selector is
  not scope enforcement.
- Workflow routing can use effective project assignment/position but records the
  qualifying evidence and still checks permission/scope.
- External portal users see only invited party/project/document/submission context
  and cannot enumerate tenant users, masters or unrelated bids.
- Support operators use an approved, expiring, purpose/scoped grant. Platform
  diagnostics must minimize tenant content and preserve access audit.

## 9. Workflow publication and execution gates

Publication validates graph reachability, valid registered commands/conditions,
domain transitions, permissions, routing, fallback, deadlines/escalation,
separation rules and tenant/project scope. Published definitions are immutable.

At execution, domain transition, work-item completion, next activation and audit
commit atomically. Locks and idempotency prevent duplicate decisions. Concurrency
conflict returns current safe state; it never silently overwrites another actor.

## 10. UI and audit obligations

- Actions show status, consequence, required reason/evidence and safe disabled
  explanation; absence from UI never substitutes for authorization.
- The workbench states why the user can act and deduplicates multiple candidacies.
- High-impact/batch/financial decisions show affected count, amount/currency,
  project, rule/version and separation warning.
- Finalized records expose revision/reversal/void/replacement, not editable fields.
- Audit retains actor membership, qualifying position/assignment when material,
  source, previous/new state, reason, timestamp/correlation and workflow version.
- Sensitive audit/export/diagnostic details require dedicated view permission.

## 11. Acceptance checklist for a new controlled capability

1. Permission code, registry entry, default-role data migration and grant decision.
2. Tenant plus project/site/object-scope enforcement in query, view and service.
3. States, allowed transitions, required fields, reversibility and finality.
4. Workflow type/template/registered command only when an actionable lifecycle exists.
5. Candidate/assignment/delegation, fallback and separation rules.
6. Transaction/lock/idempotency and atomic domain/work-item/audit behavior.
7. Cross-tenant, cross-project, unauthorized, stale-state and concurrency tests.
8. UI visibility/disabled/error/concurrency states and source/audit evidence.
9. Migration/backfill/compatibility and finalized-history preservation.
10. Reconciliation and downstream failure/retry contract where integrated.
