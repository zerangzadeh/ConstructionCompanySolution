# ADR P0-S11: Tenant lifecycle, entitlements, quotas, offboarding and support access

**Status:** PROPOSED — preparation complete; acceptance and implementation pending.
**Recorded:** 2026-09-25. **Scope:** P0.1 ADR preparation, informing P0.3 only.
**Authorization:** Product Owner requested “Execute P0-S11” with documentation-only
scope, preserving current behavior and existing worktree changes.

The accepted [P0-D05 direction](../ROADMAP_EXECUTION_PLAYBOOK.md#s03-approval-evidence-and-current-decisions)
is one core plan, versioned entitlements, justified user/project/storage limits,
warnings before the cap and blocking usage-increasing operations at the cap while
preserving authorized existing work/history/export. Subscription invoicing is
initially external. This ADR proposes the boundaries required to realize that
direction; it does not supply missing commercial parameters or approve P0.3.
The [Roadmap](../../ROADMAP.md#p03-saas-plans-entitlements-quotas-and-tenant-offboarding)
and [S03 open-input register](../ROADMAP_EXECUTION_PLAYBOOK.md#unresolved-parameters-and-latest-gates)
retain their status and gates. Future network privacy is a separate later ADR.

## 1. Verified current behavior and limits

| Evidence | Current behavior / consequence |
| --- | --- |
| [Organization models](../../apps/organizations/models.py): `OrganizationStatus`, `Organization.is_active` | States are active, suspended, cancelled and archived. Active also requires no `deleted_at` or `archived_at`. The archive-state/timestamp constraint is present; these fields alone do not implement commercial lifecycle or disposal policy. |
| [Archive migration](../../apps/organizations/migrations/0005_alter_organization_options_and_more.py): `backfill_archived_at` and constraint | Backfills archive timestamps and enforces archive-state consistency. No migration was run or environment database state inferred in S11. |
| [Organization services](../../apps/organizations/services.py): `create_organization_with_owner` | Organization, settings, initial active Tenant Owner membership and creation audit share an atomic transaction. This current function name does not merge the separate target Tenant Admin role. Starter-workflow setup is registered with `on_commit`, not durable outbox intent, as recorded in S10. |
| Services: `get_valid_memberships`, `resolve_active_organization`, `resolve_session_organization`; [middleware](../../apps/organizations/middleware.py) | Tenant selection requires active membership/role and active, non-archived, non-deleted organization. Invalid selection is cleared; middleware may then select the user's sole valid tenant. A supplied UUID does not grant access. This path offers no suspended/cancelled export session. |
| [Authorization](../../apps/organizations/authorization.py): `_validate_access_context`, `get_active_membership`, `has_business_permission`, `require_business_permission` | Active user and active organization are required. Permission helpers allow active superusers without membership after that check; membership resolution still requires membership. S07 records the different membership-required workflow paths. This is existing privileged behavior, not approved support authority. |
| Services: `update_organization_membership` | Locks organization/membership, validates Tenant and required permissions, protects the last active Tenant Owner and audits role/status changes. Tenant Owner, Tenant Admin and Tenant Manager remain independent target roles. Membership suspension/revocation is distinct from Tenant suspension/cancellation. |
| `OrganizationMembership.role_definition` and current membership services | Current schema holds one role definition per Membership and role change replaces it. This is a compatibility limitation, not the authoritative target. Target Tenant roles are zero-to-many independent Membership assignments; the same User may have a different set in each Tenant. No schema or runtime change is made by this ADR. |
| [Django Admin for Organization](../../apps/organizations/admin.py): `OrganizationAdmin` | Status/archive/delete timestamps are read-only; organization deletion is denied. This technical interface is not the Platform Admin or Tenant Admin role and does not establish a controlled lifecycle service or universal database deletion barrier. |
| Bounded search of Organizations, core and configuration | No subscription/entitlement/quota/offboarding/support-grant implementation or tenant suspend/cancel/export service was found in this boundary. The enum and access guards are not P0.3 delivery. No deployed infrastructure or all-domain lifecycle audit was performed. |

Direct [organization test bodies](../../apps/organizations/tests.py) inspected,
not executed: `test_create_organization_creates_active_owner_membership`,
`test_switch_view_rejects_unauthorized_organization`,
`test_suspended_membership_is_not_valid`,
`test_suspended_organization_is_not_valid`, `test_cancelled_organization_is_not_valid`,
`test_archived_organization_is_not_valid`, `test_soft_deleted_organization_is_not_valid`,
`test_invalid_session_organization_is_cleared_by_middleware`,
`test_membership_update_rejects_cross_tenant_record`,
`test_last_active_owner_cannot_be_revoked`,
`test_suspended_organization_settings_cannot_be_updated` and
`test_system_admin_has_global_tenant_access_without_membership`.
They establish the inspected coverage, not executed validation or evidence of
quota races, lifecycle transitions, support grants or offboarding completeness.

## 2. Ownership and alternatives

| Concern | Proposed authority and boundary |
| --- | --- |
| Tenant lifecycle and commercial access | Organizations owns tenant state, effective subscription/entitlement assignment, quota policy and lifecycle evidence. Identity remains User plus OrganizationMembership; no second tenant or permission model. |
| Membership roles | Authorization owns independent Tenant-scoped Membership role assignments and their audit history. Role-derived permissions union across active applicable assignments, then remain intersected with grants, project/site scope, delegation, workflow eligibility and policy. Composite roles and cross-Tenant role carryover are prohibited. |
| SaaS subscription administration | The named external commercial operator supplies reviewed commercial facts/references. An invoice, payment failure, spreadsheet edit or later provider callback is not itself an authorized tenant transition. The operator and approval/reconciliation process remain D05 inputs. |
| Plan and entitlement history | Versioned core-plan definitions and tenant assignments identify effective interval, capabilities, metric policy and approved change evidence. Do not overwrite the policy applied to historical operations. An entitlement enables a capability; it never grants a business permission. |
| Usage and admission | Each consuming domain owns usage source facts and enforces a shared Organizations policy server-side. Counters/read models must reconcile to source identity and tenant; they are not independent feature flags or authorities. |
| Export, hold and disposal | Organizations coordinates tenant offboarding; each domain supplies retained source/history manifests. Documents/storage owns version/blob integrity under S08; domain financial/workflow services retain finality. Export is not a cascade delete. |
| Support and operations | Support cases/diagnostics do not confer tenant access. Any later approved grant is an authorization control with explicit actor, purpose and scope, separate from ticket state and subscription support terms. |

Prefer shared policy services using existing Django/PostgreSQL transactions and
constraints when implementation is separately approved. No dependency is justified
by this proposal. Reuse the existing permission registry, audit and membership
services; own the construction-specific lifecycle and evidence rules.

| Alternative | Disposition / tradeoff |
| --- | --- |
| One core plan with effective versioned assignments | Accepted D05 direction; the exact assignment schema, limits and rollout remain proposed/open. Supports traceable policy changes without a new subscription invoicing engine. |
| Per-domain flags or commercial checks only in views | Reject as target architecture: inconsistent enforcement and direct-service bypass. A usage dashboard alone cannot enforce a cap. |
| Automatic suspension from external unpaid invoices | Not authorized. Requires accepted commercial events, reconciliation, authority and grace/error policy before any automation. Construction customer Billing/claims remains separate. |
| General membership access for offboarding/support | Do not widen current active-tenant helpers. Revised F2 selects dual-approved normal support access and a separate highly restricted emergency policy when tenant approval is practically impossible; D05/Q03/D03, named review and implementation gates remain. |
| Permanent platform impersonation or worker-Superuser authority | Not granted. E1 makes Superuser exceptional technical/system authority and requires separate explicit Tenant-data access. Platform Admin is an independent operational role and also receives no implicit Tenant business-data access; existing behavior remains a compatibility finding, not an implementation template. |

## 3. Lifecycle, authorization and transition contract

Separate tenant access state from subscription commercial phase and retention
disposition. Trial/grace concepts, if approved, must not silently become new enum
values or weaken tenant checks. Over-cap usage is a capacity condition, not automatic
suspension, cancellation or deletion. Commercial disputes do not rewrite domain
approvals, liabilities or completed workflow history.

| Tenant state / condition | Current ordinary access | Proposed policy boundary requiring acceptance |
| --- | --- | --- |
| Active | Permitted subject to existing authorization | Intersect membership, permission, S07 object scope, effective entitlement, operation-specific capacity and domain/workflow/separation rules. |
| Active at/above cap | No quota enforcement in inspected services | D05 blocks usage growth in the capped metric; preserve otherwise authorized existing work/history/export. Other dimensions and rights still apply. |
| Suspended | Excluded from normal Tenant selection and rejected by shared permission helpers | No business mutations. Any permitted read or controlled export/governance path needs explicit policy; do not claim it exists or infer it from Tenant Owner, Tenant Admin, Platform Admin or Superuser status. |
| Cancelled | Same active-tenant rejection | No normal business access. Retention, holds and lawful export obligations continue through a separately approved path, without reactivating normal access. |
| Archived or soft-deleted | Inactive/excluded | Preserve current markers. Archive is not retention expiry; soft deletion is not evidence of physical erasure. Neither authorizes purge or access restoration. |

Proposed transition requirements below define review contracts, not newly allowed
transitions. Actors, business permissions, notice requirements, effective dates,
durations and exact valid transition graph remain D05/Q04 decisions.

| Candidate transition | Required evidence and safeguards | Reversibility boundary |
| --- | --- | --- |
| Tenant creation / initial assignment | Retain atomic organization/settings/initial Tenant Owner assignment/audit creation; assign Tenant Admin, Project Manager or any other role through separate independent assignments; add only an explicitly approved effective plan assignment and quota initialization in a later package. | Failed database creation rolls back; external setup requires S10 reconciliation. |
| Active -> suspended | Authorized reason, source commercial/security decision, policy version and pending-work impact; serialize with business admission and record prior/new state. | Restoration requires a new authorized decision and checks, never a timer/invoice assumption. |
| Suspended -> active | Resolve suspension cause, validate current assignment, membership/role/scope and usage; retain original suspension evidence. | Does not restore revoked memberships, support access or previously cancelled work. |
| Active/suspended -> cancelled | Verified cancellation authority/request, effective policy and explicit export/hold/obligation assessment. No implicit destructive effect. | Cancellation reversal/re-onboarding remains undecided; do not auto-resume. |
| Cancelled -> retained/archive disposition | Governed offboarding manifest and obligation/retention review. Map to existing archive markers only through a reviewed future migration/service contract. | Archive alone cannot erase evidence or imply restored access. |
| Retained data -> authorized disposal | Q03-approved retention satisfied, no applicable hold, exact scope and independent destructive authority accepted; S08 disposal protocol. | Irreversible external deletion cutoff must be defined before enabling disposal; no ordinary “undo”. |

Future transitions must use an atomic service that locks/re-reads tenant, affected
policy and authority; validates the allowed transition and actor; stores actor,
time, previous/new state, reason, effective policy and source request identity;
and records audit atomically. Retry of the same tenant/operation/request with the
same input returns the recorded outcome; conflicting input is rejected. Serialize
membership/entitlement changes and business admission with a documented lock/version
order so concurrent suspension cannot produce a stale-authority commit. This is
an implementation acceptance requirement, not a claim about every current service.

No session, cached entitlement, claimed work item or prior support grant preserves
revoked authority. Target list/detail/direct-service/export paths must recheck the
same policy. A controlled inactive-tenant path, if accepted, needs authenticated
identity, independently validated tenant relationship and action authority; a URL
tenant ID or remembered session is insufficient. No new role, permission code,
default-role grant, Tenant Owner/Tenant Admin exception or support approver is assigned here.

## 4. Entitlements, quotas and concurrency

Versioned policy must identify its effective date, approver, metric definitions,
warning rule, cap behavior and reason for assignment/change. Prevent overlapping
ambiguous effective assignments; fail closed for unresolvable usage-increasing
admission rather than inventing an unlimited/default plan. The separately approved
cutover must define a valid assignment for every existing development tenant so
this target rule does not silently alter current behavior.

| Metric input still open under D05 | Definition that must precede enforcement |
| --- | --- |
| Users | Whether active memberships, pending users/invitations or another justified measure consumes a seat; handling of suspension, revocation, reactivation and users belonging to multiple tenants. Employee rows without login are not automatically seats. |
| Projects | Whether active, all retained or another justified project set counts; archive/reactivation/import/copy semantics. Sites and phases cannot silently become additional billable projects. |
| Storage | Logical versus physical bytes; originals/versions, quarantine/staging, derivatives, archived/held evidence, exports and backups; reconciliation and charging boundaries. A per-upload size limit is not a tenant storage quota. |
| Other capacity | Add only a justified, explicitly approved metric. S10 fairness/operating limits do not authorize commercial job quotas or background execution. |

No values, warning percentages, overage allowances, grace windows or unmetered
support users are set. Retained/held bytes may not be deleted to satisfy a cap;
archiving cannot be presumed to release capacity. Usage visibility must state the
metric, policy version, current/reserved usage, warning/block reason and approved
contact/change path without leaking another tenant's data.

Proposed admission protocol:

1. The domain declares the operation's metric delta from authoritative records,
   including reactivation/import/relationship changes; never trust a form count.
   Classify protected existing-work/history/export operations explicitly. Some
   completions append history or bytes: D05 must settle their accounting/reservation
   treatment so cap enforcement preserves the accepted protection. Do not invent
   a blanket exemption or silently block promised existing work.
2. Lock/re-read tenant lifecycle, effective entitlement and affected usage state
   inside the admission transaction. Check current authority and available capacity
   against committed usage plus valid reservations. Two concurrent admissions
   cannot both consume the same remaining capacity.
3. Commit domain change, usage/reservation effect and audit together for database
   operations. Retry by stable tenant/operation identity; rollback must not consume
   capacity twice. Release only evidenced failed/cancelled reservations, not by an
   unsupported assumption that a timeout means no external effect.
4. For file staging, coordinate durable reservations/actual byte reconciliation
   with S08 receiving/quarantine and S10 delivery identity. Partial storage/DB
   failure remains visible for recovery; quota release cannot authorize unsafe
   orphan disposal. Expiry/recovery rules require accepted parameters.
5. Reconcile counters against source records and unresolved reservations; report
   drift, retain evidence and block unsafe new admission until resolved. A lower
   future limit may leave usage above cap: preserve authorized existing work and
   history, block further growth, and apply the accepted warning/contact policy.

Policy edits require effective history and concurrency checks, not retroactive
deletion or downgrading an approved business record. A capability removal needs
explicit handling of existing records, workflow completion and exports before
cutover; it cannot be treated as a UI toggle. Exact consumer-operation classification
and permission/default-role migrations belong to the separately authorized package.

## 5. Offboarding, export and pending obligations

Propose an offboarding record tied to the tenant, request/authority, lifecycle
decision and policy versions, with an inventory of domains, document versions,
exports, holds, unresolved obligations and disposition results. Offboarding is a
coordinated process; cancellation is not its completion or a deletion instruction.

1. Validate request and export authority without reopening normal inactive-tenant
   access. Record cutoff/snapshot strategy and intended recipients. Distinguish
   subscription settlement from the contractor's project contracts, claims,
   payments, journals and other retained business history.
2. Inventory and reconcile business records, revisions, links, finalized/workflow
   evidence, audit and documents. Include unresolved deliveries and external
   receipts. Do not complete/cancel WorkItems generically or erase pending duties
   because the subscription ended.
3. Produce an authorized tenant/scope manifest with source/version identity,
   relationships, hashes/sizes for files, policy/processing provenance and explicit
   completeness status. S08 governs unsafe/missing/quarantined bytes: safe status
   evidence, no silent omission or delivery of unsafe content. A document ZIP alone
   is not a relational business-history export.
4. Recheck authority at request, generation and delivery; revoked permissions or
   changed scope invalidate/rebuild the bundle. Protected delivery, expiry and
   receipt evidence need approved parameters; request/download audit does not
   prove a recipient received a complete export. No public links or assumed Tenant Owner
   bypass. Quota must not remove the accepted authorized export protection.
5. Apply approved retention/hold policy to sources, versions, derivatives, export
   copies, audit, delivery/deduplication evidence and backups. Unknown/conflicting
   policy blocks destruction. Hold release, retention expiry, quota pressure and
   cancellation individually do not authorize disposal.
6. Serialize hold placement with the irreversible disposal cutoff under S08;
   record exact authorized intent and per-copy outcomes. Partial failure remains
   pending; do not promise immediate erasure from immutable backups. Restoration
   must reinstate lifecycle, holds, restrictions and disposition evidence before
   access, and reconcile S10 receipts/keys before dispatch resumes.

Tenant offboarding must not delete the global User or disable access to unrelated
tenant memberships. Keep User, Employee and tenant membership identities distinct;
any identity-retention decision needs its own accepted policy.

[S10 authority contracts](ADR_P0_S10_ASYNC_OUTBOX_IDEMPOTENCY.md#5-authority-tenant-lifecycle-and-privacy)
apply throughout: deferred user commands recheck current authority; an already
committed obligation needs its own accepted continuation/cancellation authority;
maintenance/export/retention has explicit purpose and lifecycle scope. Until such
contracts are approved, block execution and surface the unresolved obligation.
Do not silently discard intent, reset its identity, replay an uncertain external
effect or substitute a worker credential for business authority. Cancellation
cannot undo already accepted external effects; domain corrections remain required.

## 6. Support access and separation

[S07 privileged-path evidence](ADR_P0_S07_PROJECT_SITE_AUTHORIZATION.md#4-privileged-paths-and-separation-unresolved-not-exceptions)
remains unchanged at runtime. Revised F2 records policy direction but implements no
support grant or emergency mechanism. Normal access requires simple, understandable
approval by an authorized tenant user plus independent platform approval, and must
be purpose-, scope- and time-limited, revocable, attributable and fully audited.
A plan's support level supplies neither consent nor permission; technical database
or storage access is not tenant authorization.

Before accepting the latter option, define requester/operator identity, tenant
consent and independent approver, exact actions and project/site/data scope,
effective interval, revocation, jurisdiction and audit visibility. No duration,
grant recipient or approver identity is selected. D03 must settle support-access
locations/operator arrangements. Named security/operations/privacy and conditional
legal review remains open.

When tenant approval is practically impossible during a genuine emergency, revised
F2 permits design of a separate highly restricted path with multi-stage or
independent platform approval, recorded reason, minimum scope, short explicit
validity, complete audit, actor attribution, automatic expiry/revocation and no
hidden impersonation. This is not standing access, an implemented exception or
background authority.

Proposed controls if that option is later accepted: explicit visible tenant/support
context; original operator attribution without shared credentials or concealed
impersonation; rechecks on every action/download and queued continuation; immediate
denial after expiry/revocation; no self-grant, scope expansion, re-grant or business
approval derived from support status. Export, mutation and financial/workflow
actions require their own accepted authority and ordinary domain invariants.
Suspension/cancellation does not prolong a grant or provide recovery access.
No emergency fallback may activate merely because the ordinary path is blocked.

Minimize/redact diagnostics and keep tenant data out of unscoped logs or support
attachments. Record consent/approval, purpose, scope, operator, start/end/revocation,
actions and results under approved retention. Audit is append-only evidence, not
a credential, support conversation store or notification queue. Q03 decides
retention and lawful export visibility; absence of audit evidence cannot be cured
by performing an unrecorded privileged action.

## 7. Acceptance gates and compatible implementation sequencing

| Open input | Required decision / latest gate |
| --- | --- |
| D03 | Permitted primary/backup/log/document/support jurisdictions, provider, named operator/incident owner, coverage and budget; before P0.2 implementation, hosting commitment or data placement. |
| D04 | Numeric loss/outage objectives, units, scenarios/service hours, contractual applicability and recovery owner; before recovery implementation/customer promises, with measured restore evidence before P10.3. |
| D05 | Metric definitions/values, warning/overage/upgrade, protected-completion accounting, trial/grace/suspension/cancellation/re-entry, pricing/support terms and external invoicing operator; before P0.3 policy implementation, commercial terms before sale. |
| Q03 | Signature/evidence, retention/hold/export/disposal obligations and responsible approver; before affected storage/DMS/offboarding design acceptance or data placement. |
| Q04 | A1/B1/C1/D1/E1, revised F2, final G3 — Revised with Protected Operations, and H1 are selected. Support/emergency self-approval is protected; named security/workflow and conditional operations/privacy/accounting/legal/domain reviews remain before accepting S07/P1.1 or affected lifecycle/support controls. |
| Execution/operations acceptance | Named reviewers and operation-specific background authority, export completeness, quota reservations, disposal cutoff and restore/reconciliation contracts under S07/S08/S10; before enabling each operation. No background exception is inferred. |

Carry all other S03 inputs to their original gates; S11 does not resolve D01,
Q01/Q02, accept prior ADRs, freeze release scope or complete P0/P0.1.

Only after policy/ADR acceptance and a separately approved implementation package:

1. Inventory affected entry points and direct services, existing tenant states,
   usage sources and pending obligations. Define permission catalogue/default-role
   migrations for new access-controlled capabilities using the existing registry.
2. Expand version/history and usage/reservation structures with tenant constraints;
   no model or migration is prescribed as already delivered. Review explicit
   existing-tenant assignments and data reconciliation; never assume unlimited
   entitlement, an empty database, new broad grants or safe automatic cancellation.
3. Compare policy decisions without enforcement first, reconcile counts and
   protected operations, and rehearse tenant-scoped export/hold/restore behavior.
   Choose one bounded rollout slice and coordinate all its admission paths.
4. Switch only after authorization/atomicity/isolation and quota-race tests pass.
   Rollback retains history, held evidence and restrictive decisions; it must not
   reactivate cancelled tenants or erase pending obligations. Legacy fields stay
   until deployment/backfill/dependency/retention checks pass and removal is
   explicitly approved. Every environment runs its approved migrations.

## 8. Static design walkthroughs and validation limits

These are reviewed design cases, **not executed application tests**:

| Case | Proposed expected outcome |
| --- | --- |
| Forged tenant UUID or foreign membership/export request | Deny; no tenant names, totals, manifests or object-existence leakage. |
| Tenant/initial Tenant Owner creation fails partway | Database Tenant/settings/initial Tenant Owner/audit roll back together; no assumed durable post-commit delivery. |
| One of several Membership roles is revoked | Revoke only that assignment, retain the others and its actor/Tenant/role/time/reason evidence, then re-evaluate effective authorization; do not suspend the Membership or infer removal of another role. |
| Shared User has roles in two Tenants | Lifecycle, quota, export, support and role changes in one Tenant do not alter the other Membership or its independent role assignments. |
| Two seat/project admissions compete for remaining capacity | Serialize under one effective policy; no double consumption, retries do not reserve twice. |
| Upload stores bytes but database finalization fails | Retain reservation/reconciliation evidence under S08; do not count success or delete by age alone. |
| Limit decreases below existing usage; completion appends history | Block new growth, retain history and protected work/export; resolve D05 accounting before enforcement, no invented exemption. |
| External subscription invoice is late or disputed | No automatic tenant transition, deletion or mutation of construction Billing history. |
| Suspension races with business mutation or entitlement update | Re-read/serialize tenant and authority; no stale-authority commit or partial audit. |
| Cancelled tenant still has liabilities, held records or pending deliveries | No ordinary access or automatic discharge; preserve evidence, block unapproved execution and surface obligations. |
| Export requester loses authority before delivery or manifest has missing bytes | Invalidate/rebuild or deny; explicit completeness failure, no unsafe/public bundle. |
| Legal hold races with disposal; one storage copy fails deletion | Serialize before irreversible cutoff; no prohibited deletion or false completion, retain unresolved results. |
| Tenant Owner/Tenant Admin/Platform Admin/Superuser/support requests bypass, or a grant expires mid-task | D1/E1/F2 create no role-derived or standing bypass; current behavior remains until separately authorized implementation, and per-action rechecks/expiry apply. |
| Restore revives cancelled tenant data or already-delivered intent | Apply restrictions/holds/disposition first; pause dispatch for receipt/key reconciliation, no blind replay. |
| Offboard one tenant of a shared User | Preserve unrelated memberships and global identity; scope all manifests and effects to the authorized tenant. |

Future implementation needs service/view parity, tenant and object negative tests,
independent role assignment/revocation and permission-union tests, cross-Tenant
role isolation, membership/entitlement/lifecycle concurrency, quota reservation/
retry/reconciliation, export completeness/revocation, hold/disposal races, support
anti-escalation and restore exercises. S11 performs only local link/anchor,
evidence-reference, decision/status consistency, design-walkthrough, whitespace and
worktree-preservation validation. No runtime, infrastructure, legal/commercial,
load, recovery or professional approval is certified.
