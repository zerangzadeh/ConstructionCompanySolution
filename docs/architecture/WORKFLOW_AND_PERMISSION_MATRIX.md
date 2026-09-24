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
+ active/non-blocking Organization state
+ entitled capability/quota [target]
+ required BusinessPermission
+ project/site/object scope [target]
+ valid domain state and required data
+ current WorkItem assignment/candidacy/delegation [workflow action]
+ separation-of-duties and effective-position evidence [when configured]
= authorized domain service command
```

The domain service re-reads and re-authorizes inside the transaction. UI
visibility, possession of an ID, `Employee`, `Position`, department/team,
candidate membership or superuser convenience is not ordinary business authority.

## 3. Permission ownership

- `BusinessPermissionCode` and `permission_registry` define application
  capabilities; default-role grants are data-migrated and tested.
- Organization roles compose permissions. Current protected role codes remain
  code-authoritative until the approved canonical role migration.
- Target responsibility profiles are Owner, Admin, Manager, Accountant,
  Supervisor and Viewer. These are default-policy concepts, not hard-coded checks.
- Project/site grants can only restrict/intersect tenant permission. They do not
  create a second permission catalogue.
- Workflow position routing records who was responsible. It never grants the
  underlying business permission.
- Every sensitive export, archive, void, reversal, close/reopen, support access,
  payroll/financial view and approval may require a distinct permission.

## 4. Typical target default-role policy

This matrix guides future default grants; it does not override the current role
catalogue or eliminate per-capability/SoD design.

| Capability family | Owner | Admin | Manager | Accountant | Supervisor | Viewer |
| --- | --- | --- | --- | --- | --- | --- |
| Tenant lifecycle/ownership/plan/export | Govern | Configure limited | No default | No default | No default | Read own context |
| Membership/role/object scope | Govern/protect owner | Administer delegated grants | Scoped delegation | No default | No default | No |
| Shared masters | Govern | Manage | Manage scoped | Read/use; sensitive party/bank as granted | Read/use scoped | Read scoped |
| Projects/operations | Govern | Configure | Manage/approve scoped | Read financial context | Record/review assigned site | Read scoped |
| Contracts/claims/procurement | Govern exceptional | Configure | Manage/approve configured | Financial review/posting, not automatic technical approval | Request/record assigned operations | Read scoped |
| Accounting/Treasury/Payroll | Oversight, not automatic maker+checker | No default sensitive approval | Budget/commercial approval only as configured | Prepare/review/post/reconcile with SoD | Time/site inputs only | Highly restricted read |
| HSE/Quality | Oversight | Configure | Manage scoped | Read cost/compliance as granted | Report/inspect/act assigned | Read scoped/sensitive limits |
| Workflow administration | Publish only with dedicated permission | Configure delegated | Domain policy as granted | Financial workflow as granted | Act on assigned items | No action |
| Audit/export/support access | Oversight with dedicated permission | Operational limited | Scoped evidence | Financial evidence | Own/scoped evidence | Read only if granted |

An Owner cannot bypass statutory, close-period, maker-checker or independent
verification rules merely because ownership is broad. Emergency override, if ever
approved, needs a separate permission, reason, alert and audit.

## 5. Delivered lifecycle matrix

Exact service names/statuses may evolve; consult models/services/tests before
implementation work.

| Domain aggregate | Delivered lifecycle/action | Required authority pattern | Finality/correction |
| --- | --- | --- | --- |
| Organization | active/suspend/cancel/archive and settings/membership operations | System/owner or dedicated tenant-governance permission; owner protection | Lifecycle and export/retention evidence audited |
| Membership/role | provision/connect, assign/change, suspend/revoke | Membership-management permission; cannot grant capabilities actor lacks; elevation audited | Effective history; final owner protected |
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
| Expense | recorded -> void | Expense record/void permission | Original amount immutable; reasoned void |
| Payment/allocation | posted -> void; allocation active -> reversed | Payment/allocation/void/reverse permission | Cash evidence and allocation reversals retained |
| Document/version/link | add version/link, archive, view/download | Document permission plus view access to every linked context | Versions/links immutable; archive instead of destructive delete |
| Safety incident | report -> review -> assign -> corrective action -> resolve -> close | HSE permission + work-item responsibility + responsible-party checks | Closed immutable; audit/reopen only if separately designed |
| Quality issue | report -> review -> assign -> corrective action -> verify -> close | QA permission + work-item responsibility; verifier evidence | Closed immutable; verification/closure evidence retained |
| Baseline | draft -> approved/superseded | Baseline permission + workflow assignment/candidacy | Approved baseline immutable |
| Progress record | draft -> submitted -> verified/rejected/corrected | Record/verify permission + distinct work item | Verified source immutable; correction links replacement |
| Progress claim | draft -> submitted -> approved/returned revision | Claim permission + eligible approver/candidacy + separation | Submitted snapshot frozen; approved/returned revision immutable |
| Claim settlement | allocate -> reverse | Settlement permission; approved claim and compatible payment allocation | Append/reverse; never synthesizes cash |
| Workflow definition/version | draft configuration -> publish | Dedicated workflow-admin/publish permission | Published version immutable |
| Work item | offer/claim/release/act/reassign/delegate/complete | Underlying domain permission + candidacy/assignment + separation | Assignment/decision history append-only |

## 6. Target workflow matrix

| Roadmap capability | Principal states/decisions to design | Permission/SoD requirements | Roadmap |
| --- | --- | --- | --- |
| Tenant plans/offboarding | entitlement change, grace/suspend/cancel, export/hold/delete decision | Owner/platform split; export and destructive retention separate; no support bypass | P0.3 |
| Object-scope grants | propose/grant/change/revoke/emergency access | Cannot self-elevate; grantor must hold delegated authority; full audit | P1.1 |
| Regulatory rules | draft/review/activate/supersede | Legal/accounting reviewer; maker cannot be sole activator where required | P1.2 |
| Material/technical approval | draft/review/approve/reject/archive/substitute | Master-data vs technical/quality approval separation | P1.4 |
| Journal/period close | propose/review/post/reverse; open/close/reopen | Maker-checker; close/reopen and reversal dedicated; source idempotency | P2 |
| Treasury/AP/AR | propose/approve/release/clear/reconcile/write-off | Bank/account sensitivity; maker-checker; allocation/write-off limits | P3 |
| Estimate/BOQ/budget | import/validate/revise/compare/approve/handoff/rebaseline | Estimator vs approver; accepted handoff explicit; approved versions immutable | P4.0/P4.1 |
| Expense | draft/submit/approve/return/void/allocate/settle | Requester vs approver; budget/duplicate controls; finance settlement distinct | P4.3 |
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

## 7. Separation-of-duties baseline

Every package explicitly decides whether the following are prohibited, allowed
only for small-tenant owner fallback, or configurable with documented risk:

- creating and approving the same procurement, expense, claim or journal;
- preparing and releasing the same payment/cheque/transfer;
- recording and verifying the same progress/inspection/test;
- calculating and finalizing the same payroll run;
- administering a rule/workflow and approving a transaction affected by it;
- granting one's own role/scope/elevation or support access;
- reporting/investigating/closing the same HSE/QA case; and
- creating and resolving the same reconciliation exception.

Fallback requires the underlying permission, lack of another eligible actor when
policy permits it, explicit reason and retained evidence. It never bypasses legal,
period-close or independent-verification requirements.

## 8. Project/site and external scope

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
