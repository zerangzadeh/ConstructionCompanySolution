# Workflow and Permission Matrix

**Status:** cross-domain policy reference; exact current transitions and grants remain code/test authoritative

**Workflow architecture:** `TENANT_WORKFLOW_AND_WORK_MANAGEMENT.md`

**User goals:** `USER_CAPABILITY_MAP.md`

**Current V1 role reconciliation (2026-10-22):** the Human
[Product Decision](../governance/uiux/authorization_reconciliation/PRODUCT_DECISION.md)
authorizes explicit operational/specialist catalogue mappings and the bounded
Platform Initial Grant. The complete
[Role-Permission Matrix](../governance/uiux/authorization_reconciliation/ROLE_PERMISSION_MATRIX.csv)
reflects `role_defaults.py` and `role_reconciliation.py`. Historical statements
below about unassigned default permissions are superseded only for those explicit
catalogue mappings. Tenant Owner/Admin receive no additional permissions.
Unresolved domain activation, financial/SoD policy and statutory gates remain
closed; catalogue assignment alone does not activate them.

An existing active Platform Admin may assign an active approved role to an exact
active Tenant membership and explicit scope only when the ordinary delegation
path has no lawful delegator/independent tenant approver pair. The dedicated
`platform_initial_grant` service forbids self-grants, checks existing scope union,
re-reads authority under locks and records correlated before/after audit evidence.
It requires no second Platform approver and creates no Tenant authority for its
actor. Ordinary `assign_membership_role()` retains its existing contract.

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
- Protected role codes remain code-authoritative. Current authorization supports
  multiple independent Membership role assignments and explicit Organization,
  Project and Site grants; the legacy single-role reference remains for reversible
  permission read compatibility. A Membership with no effective same-Tenant scope
  grant is denied by shared service, queryset and Admin checks. An explicit
  Organization grant is required for broad Tenant scope; a legacy role alone does
  not supply it. This is the CEP-001 implementation boundary.
- Project/site grants can only restrict/intersect tenant permission. They do not
  create a second permission catalogue.
- Django Admin Tenant inspection requires active Tenant membership, a mapped
  business view permission and object scope; unmapped Tenant Admin models fail
  closed. The Company/Project/Site Admin views use the shared scope queryset,
  and related-field list filters are suppressed where they could enumerate
  out-of-scope choices. Platform-only role and audit Admin lists exclude Tenant
  rows; Superuser or Platform Admin status does not supply Tenant data authority.
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
| Expense master data | Platform expense group create/update/archive; tenant expense-category create/update/archive | Platform Admin manages the global `PlatformExpenseGroup` catalogue without tenant-data access. Tenant Owner and Tenant Admin receive the tenant-scoped `expense_categories.view/create/change/archive` permissions; services re-check active membership and organization scope. | Platform master actions and tenant master actions are audited; a group code with linked history cannot change, and a group with active tenant categories cannot be archived. |
| Payment/allocation | posted -> void; allocation active -> reversed | Payment/allocation/void/reverse permission | Cash evidence and allocation reversals retained |
| Document/version/link/photo | add version/link, archive, view/download; employee self-access; capture/upload Project Gallery photos | Existing document permission plus view access to every linked Project/Site/business context; CEP-011 employee self-access additionally resolves the same-tenant Person and current WorkRelationship, requires employee category current/history policy and own source link, and rechecks `DOCUMENTS_DOWNLOAD` plus category download policy for bytes. Qualification/training evidence needs explicit unambiguous legacy mapping. UI visibility grants nothing. Gallery composes project and document permissions. | Version instance guards, fail-closed processing, protected preview and archival; ended-episode history requires a current same-Person episode and category history permission. No acknowledgement lifecycle or inferred legacy backfill. Camera and multi-upload share DMS ingestion, links are registered/retained, and Gallery owns no bytes. |
| Safety incident | report -> review -> assign -> corrective action -> resolve -> close | HSE permission + work-item responsibility + responsible-party checks | Closed immutable; audit/reopen only if separately designed |
| Quality issue | report -> review -> assign -> corrective action -> verify -> close | QA permission + work-item responsibility; verifier evidence | Closed immutable; verification/closure evidence retained |
| Baseline | draft -> approved/superseded | Baseline permission + workflow assignment/candidacy | Approved baseline immutable |
| Progress record | draft -> submitted -> verified/rejected/corrected | Record/verify permission + distinct work item | Verified source immutable; correction links replacement |
| Contract term version | draft -> approved -> superseded | `contract_terms.manage/approve`; author cannot approve same version; Tenant/project scope | Approved/superseded terms immutable and historically resolvable |
| National regulatory policy version | draft -> published -> retired; direct effective-date resolution | Platform Admin provenance/review/publication authority; external source and accepted review evidence required; national rules are not Tenant-selectable or overrideable | Missing/unverified/unpublished/ineffective applicability fails closed; no inferred statutory values |
| Progress claim | draft -> submitted -> approved/returned revision | Claim permission + eligible approver/candidacy + separation | Submitted snapshot freezes party, currency, term/rule versions, calculation and sources; approved/returned revision immutable |
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
| RFQ/quote/award/invoice match | issue/invite/submit/close/custody/open/admissibility/compare/award/PO-change/receive/service-accept/invoice/match/discrepancy/read-only review | P5-S07–S17 controls remain mandatory. Every operation and P5-S27 review is Tenant/project/object/version scoped. `invoice_matches.view` exposes immutable run, line, policy lineage and discrepancy evidence only. Missing policy/evidence fails closed; no force-match or material discrepancy override exists. Match review never releases a payable, posting, cost, stock or cash action. | P5.1; P5-S01–S27 complete/accepted; P5-S28+ unauthorized |
| External portal | create invitation/accept/read exact RFQ/submit revision/revoke | P5-S18–S27 require a default-ungranted internal management permission, expiring token-hash invitation, one unambiguous active account with matching invited email, no active internal membership, active Tenant, exact supplier/RFQ invitation and unrevoked immutable grant. Email rebinding and identity ambiguity fail closed. Only issued RFQ snapshot facts are readable; private/no-cache UI submission uses an opaque stable retry key and existing sealed revision/succession evidence. Correction is a permitted resubmission; withdrawal is unavailable. No internal notes, competitor data, generic documents, external sealed-evidence upload, downstream authority or support bypass. | P5.2 P5-S18–S27 complete/accepted; P5-S28+ unauthorized |
| Receivable claim / financial handoff | term draft/approve; claim create/submit/approve/return/revise; linked replacement/cancellation; explicit AR recognize | P6-S01–S13 rechecks Tenant/project permission, workflow candidacy and SoD inside locked transactions. Final claim history is immutable; AR recognition uses the existing separately permissioned idempotent subledger service and never occurs on approval. Corrections fail closed after settlement/AR until controlled downstream reversal is authorized. | P6-S01–S13 Product Owner accepted; automatic AR/journal gated |
| Payable subcontract certificate / financial handoff | payable term draft/approve; measured-work record/verify; certificate create/submit/approve/return; retention/advance/back-charge; linked replacement/cancellation; explicit AP recognize | P6-S14–S20 uses dedicated permissions, Tenant/project scope, direct measurement maker-checker, shared-workflow candidacy and strict submitter/approver SoD. Certificate approval, work-item completion, correction disposition and audit evidence are atomic. Final history is immutable; AP recognition is explicit and separately permissioned, and corrections fail closed after AP recognition. | P6-S14–S20 Product Owner accepted; automatic AP/journal remains gated |
| Guarantee / insurance-clearance / retention release | create/submit/approve/return; correct/renew/release; expire due dated evidence; calculate separated exposure; replace/cancel retention release | P6-S21–S25 uses dedicated permissions, Tenant/project/contract/party/document scope, shared-workflow candidacy, strict submitter/approver SoD, row locks and atomic domain/work-item/audit transitions. Final versions are immutable. Missing approved term authority, required clearance, safe DMS evidence or retained balance fails closed. Expiry is an evidence fact; issued and received exposure is never netted. | P6-S21–S25 Product Owner accepted; Article 38 effects and AP/AR/Accounting/Treasury/provider/notification behavior remain gated |
| Taxpayer invoice / contractor compliance | create/preflight/submit/approve/return; export or invoke explicit test adapter; record accepted/rejected/provider-error evidence; authorize retry or close; correct/cancel through linked versions | Dedicated view/prepare/submit/approve and submission execute/resolve permissions; Tenant/project/contract/party and reviewed effective-policy alignment; shared-workflow candidacy with strict submitter/approver SoD; locked, idempotent attempt allocation; immutable finalized and attempt history; explicit human retry ownership; credential-like persisted keys rejected. External acceptance never mutates the commercial source or substitutes for AR/AP/GL reconciliation. | P6-S26–S32 Product Owner accepted. Official schemas/values, live credentials/provider transport, Article 38/legal/accounting effects, automatic finance and production activation remain gated. |
| Contractual change / Claim / EOT | create/submit/approve/return; withdraw; correct or cancel through a linked superseding version | P6-S33–S38 uses dedicated view/prepare/submit/approve permissions, exact Tenant/project/contract/party scope, shared-workflow candidacy, strict submitter/approver SoD, row locks, idempotency, atomic audit, immutable finalized history and typed source-version evidence. Entitlement, approved amount, delay responsibility and EOT days are explicit decisions only. | P6-S33–S42 Product Owner accepted, including the read-only review/closeout. No automatic contract/amendment, budget, schedule, Billing, AP/AR, subledger, GL, Treasury/cash or production effect; P7+ unauthorized. |
| Qualification/training | record immutable evidence; revoke/supersede; derive expiry; record training/performance | P7-S01–S05 uses Workforce and DMS permissions, tenant/project scope and default-denied performance/labor-rate access. Qualifications, skills and positions never grant permission; no approval workflow or financial consumer is activated. | P7-S01–S05 Product Owner accepted; later capability does not alter this boundary |
| Time and attendance | configure calendar/shift; capture/import/finalize/correct/reconcile attendance; request/review leave, mission and overtime; prepare/submit/review timesheet; retain non-posting preview | Explicit permission plus membership and project/site scope. Capturer/requester/preparer cannot perform the corresponding review; finalized facts change only through reasoned correction/reversal/supersession. Position, qualification and Workforce assignment never grant permission. | P7-S06–S12 Product Owner accepted; provider/self-service/payroll/cost/financial effects excluded |
| Core Payroll | configure effective pay/rules; prepare/lock/calculate; review; finalize; view/export payslip; adjust/reverse/replace | Dedicated default-denied permissions, Tenant/project/site scope where applicable, row locks, immutable snapshots/results, idempotency and atomic audit. Preparation, review and finalization are separate; the same user may perform them only when explicitly granted all required permissions. Locked runs pin authoritative monetary policies. Payslip export is permission-gated, POST-only and audited; Core audit permission does not reveal statutory events. | P7-S01–S36 accepted and complete within documented non-production boundaries. Posting, payment, Project Cost actual, P8 implementation and production effects remain unauthorized. |
| Statutory Payroll Tax / employee insurance | view Platform authority; prepare/review calculation; record allowed employer/workshop/employee identifiers; generate original/correction/cancellation output; record export/status/error; authorize retry/resolve; reconcile | P7-S23–S28 uses independent default-denied statutory permissions, active membership and Tenant scope. National values/schemas are Platform-owned and resolved directly by effective date; source plus accepted review are mandatory. Calculations, identity evidence, outputs, attempts, resolutions and reconciliation are immutable/version-pinned. Same-user regulatory lifecycle is allowed only with each explicit permission; Tenant override/selection is forbidden. | Product Owner accepted. Missing authority/schema/identity fails closed; live filing, credentials, AP/Accounting/Treasury/cash/Project Cost and production activation remain gated. |
| Payroll financial handoff | prepare/review liability, Accounting-source, Treasury-payment and Project Cost proposals; record/review reconciliation evidence | Ten default-denied permissions separate preparation/review for each family and reconciliation. List/detail visibility is limited to explicitly authorized families; reconciliation permission has deliberate cross-family evidence scope. Immutable finalized-source and correction lineage, stable idempotency and row locking apply. | P7-S01–S36 accepted and complete within documented non-production boundaries. Missing mapping, payee/payment authority, allocation or acknowledgment fails closed. AP/subledger recognition, journals/GL, payment/cash, Project Cost actual, P8 implementation and production behavior remain inactive. |
| Inventory reservation/traceability/count/transfer | reservation draft/activate/fulfill/release/cancel; bin/lot/serial/expiry/quarantine; count freeze/count/submit/approve/post; transfer dispatch/in-transit/accept/exception | Dedicated view/manage/release, traceability view/manage/dispose, count view/prepare/approve/post, transfer view/prepare/dispatch/independent accept/resolve and reconciliation permissions are implemented. Active Tenant membership plus warehouse/project scope is mandatory; custody/workflow/position never grants permission. | P8-S05–S11 Product Owner accepted; no valuation or downstream effects |
| Inventory valuation | acquire/value/issue/return/transfer/reverse/reconcile | Default-deny cost-sensitive view and separated prepare/approve/reverse/reconcile/supply roles; operational quantity authority remains separated from monetary policy, Accounting posting and Project Cost consumption; immutable layer correction | P8-D01=A; P8-S12–S17 Product Owner accepted within non-production boundaries |
| Equipment maintenance/spares | plan/authorize/start/complete/correct work; reference/reconcile posted issue/return parts | Equipment owns work; Inventory owns part custody; Procurement/AP own external service/invoice evidence; no completion-time stock mutation. Dedicated operational permissions, reasoned correction and maker-checker controls apply. | P8-D05–D06=A; P8-S18–S23 Product Owner accepted within non-production boundaries |
| Equipment cost / Fixed Assets | prepare/review/reverse Equipment allocation proposals; asset candidate/capitalize/depreciate/impair/transfer/dispose; prepare/review/reconcile handoff proposals | Dedicated default-deny Equipment-cost and Fixed-Asset permissions preserve operational/asset/Accounting/Project Controls separation. Policy publication, capitalization, depreciation finalization, transactions and reversal enforce maker-checker, tenant scope, locking, immutable reversal/replacement and source reconciliation. No P8 action grants journal posting or actual recognition. | P8-S01–S30 Product Owner accepted under C01–C38=A and complete within documented non-production boundaries; production activation gated |
| Field/document control | P9-S01–S05 field-observation draft/capture/evidence-submit/review/accept-or-reject/correct-or-supersede; prepare/review source-only proposal | Explicit field permissions, tenant/project/site scope, independent reviewer, immutable submitted observation and exact DMS-version pin; DMS alone owns bytes/versions; no downstream consumer mutation | P9-S01–S05 implemented within accepted P9-D01–D12=A boundary; HSE/QA runtime is separately governed by the next row |
| HSE/QA | P9-S06–S11 typed template/inspection, permit, QA test/result, finding/NCR, CAPA, verification/effectiveness/close/reopen; later investigate/escalate/knowledge | Explicit capability permissions and tenant/project/site scope; implementer cannot self-verify; distinct closer only when pinned policy requires; separate sensitive DMS-evidence permission | P9-S06–S25 Product Owner accepted; S26 closeout complete; P10-S14–S17 closeout controls may read with source permission but cannot mutate HSE/QA. |
| Partner qualification/performance | submit/review/approve/evaluate/appeal/expire/suspend; no new generic block semantics | Evidence/reviewer conflict; explainable score and category/time scope; existing PartyRestriction remains separate | P9-S12–S15 Product Owner accepted; `P9-P01`–`P9-P18=A` |
| Support/access | open/triage/in-progress/awaiting-requester/resolve/close/reopen; request/Tenant-confirm/independent-platform-approve/use/expire/revoke | Explicit tenant permissions, recipient-only acknowledgement, registered source plus active recipient, open-time source revalidation, exact retry, locked stale-state transitions, exact/sensitive DMS evidence controls, immutable events, derived calendar facts and time/purpose/scope revalidation; no implicit Platform Admin tenant access | P9-S16–S25 Product Owner accepted; `P9-N01`–`P9-N18=A`; providers and downstream effects remain unauthorized |
| Knowledge | draft/submit/review/request correction/recommend/approve/publish/supersede/withdraw; request/review/approve/publish sanitized Platform promotion; record/correct recurrence and reuse | P9-S21–S24 Product Owner accepted under `P9-K01`–`P9-K24=A`: exact typed source/DMS pins revalidated at consequential boundaries, immutable submitted/published/correction history, author cannot approve/publish own revision, sensitive/Platform promotion independent approval, Tenant/Platform scope separation, no downstream effects; AI cannot publish | S25 cross-domain assurance Product Owner accepted; S26 closeout complete; P10-S14–S17 treats missing exact project provenance as gated/unavailable and cannot mutate Knowledge. |
| Reporting reconciliation and exceptions | publish immutable pair version; execute/review run; assign/disposition/close/reopen exception; exact replay/successor/projection check | P10-S07–S13 controls are default-deny and Tenant/object scoped; pair author cannot publish, material runner cannot review, and the last disposer cannot solely close a material/integrity/security exception. Source correction requires source-domain authority. Assignment grants no permission, DMS owns bytes, and every source/evidence drill-through is re-authorized. | `P10-R01`–`P10-R36=A`; P10-S07–S13 Product Owner accepted for exactly 13 pairs. No source mutation, downstream effect or production authority; S14–S17 consumes only its immutable control evidence. |
| Governed reporting | code-governed definition/version; explicit synchronous refresh; independently review material financial result; view scoped dashboard; drill through; create/download bounded export | Sixteen default-denied Reporting permissions plus active Tenant membership and object scope; source-domain permission is required at refresh and rechecked at drill-through; material runner cannot review own result; Platform Admin has no implicit Tenant access; exports store no bytes | P10-S02–S13 Product Owner accepted; its authority remains unchanged by closeout coordination. |
| Project-closeout coordination | prepare/publish profile; prepare/coordinate/view case; capture immutable assessment; review/accept/reject/reopen through append-only events; link exact DMS evidence; create/download private byte-free export | Fourteen new default-denied permissions; active Tenant membership and project/object/source scope are rechecked. Author cannot publish; preparer and last material disposer cannot solely accept; exact stale revision/source hash and locks protect transitions. DMS alone owns bytes; sensitive/drill-through/export paths reauthorize. | `P10-C01`–`P10-C36=A`; P10-S14–S17 Product Owner accepted. Reporting is derived-only and cannot mutate source or downstream state; P10-S18+ and production remain gated. |

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
- calculating and finalizing the same payroll run is a configurable conflict in
  larger Tenants, but P7-S13–S22 intentionally permits the same user when that user
  explicitly holds every separate Payroll permission; this does not alter other
  domain Self-Approval rules;
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
