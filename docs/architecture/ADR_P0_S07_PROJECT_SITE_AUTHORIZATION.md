# ADR P0-S07: Project/site authorization and workflow intersection

**Status:** PROPOSED — preparation complete; acceptance and implementation pending.
**Recorded:** 2026-09-25. **Scope:** P0.1 / PPC-04; P1.1 remains PLANNED.
**Authorization:** Product Owner requested S07 and this ADR only, preserving current
behavior, without P1.1 implementation or invented privileged/support exceptions.

This proposal develops [Roadmap P1.1](../../ROADMAP.md) and the target
[authorization equation](WORKFLOW_AND_PERMISSION_MATRIX.md#2-authorization-equation).
It does not implement grants, role migrations, Tenant Owner fallback or support access.
The [P0-S15 Q04 selections](P0_S14_Q04_PRODUCT_OWNER_DECISION_PACKET.md#5-product-owner-response-record)
now supply Product Owner policy direction; accountable reviewer names/evidence and
formal acceptance remain open. Other inputs retain their original gates. Models,
migrations and tests remain authoritative for delivered behavior.

Role terms in this ADR follow the authoritative split: Superuser and Platform Admin
are independent platform roles; Tenant Owner, Tenant Admin / Local Admin and Tenant
Manager are independent Tenant roles. A user may explicitly hold multiple
roles, but no role implies, merges or inherits another. Current role codes and
Superuser shortcuts remain compatibility evidence until separately migrated.
Tenant/business roles are target membership-scoped many-to-many assignments, so
the same User may hold different role sets in different Tenants. Common
combinations do not become composite roles.

## 1. Verified current behavior

| Evidence | Current behavior and boundary |
| --- | --- |
| [Organization services](../../apps/organizations/services.py): `get_valid_memberships`, `resolve_active_organization`, `resolve_session_organization`; [middleware](../../apps/organizations/middleware.py) | Session selection resolves through active membership/role and active, non-archived, non-deleted organization; invalid selection is cleared. This is tenant selection, not project/site authorization. |
| [Authorization](../../apps/organizations/authorization.py): `get_active_membership`, `has_business_permission`, `require_business_permission` | Active user and organization checks precede permission checks. Ordinary users need active membership/role and an active permission grant. Active superusers pass the latter two helpers without membership (`require_business_permission` returns `None`). This existing service path is not a new support policy or proof of equivalent HTTP access. |
| [Project selectors](../../apps/projects/services.py): `get_organization_projects`, `get_organization_project_sites`, `get_organization_sites` | Tenant/domain permissions and organization/parent filters apply. No per-user project/site grant intersection exists in these selectors. A valid same-tenant project relationship alone does not establish restricted object authority. |
| [Workbench](../../apps/workflows/workbench.py): `_authorized_membership`, `_base_queryset` | Requires work-item view permission and an active membership even for superusers; superusers receive all permission codes for adapter filtering. Items are filtered by tenant, permitted subject type and assignee/open candidacy. This is not the proposed project/site scope layer. |
| [Runtime](../../apps/workflows/runtime.py): `_require_permission`, `complete_work_item` | Runtime always obtains a membership, including privileged actors. Completion locks runtime state, repeats work-item permission checks, requires the claimed assignee and active candidate, checks configured separation and the resolved domain permission through `membership_has_permission`, then invokes the registered domain command. |
| [Routing](../../apps/workflows/routing.py): `resolve_step_candidates`; runtime `_check_sod` | Routes merge/deduplicate memberships and retain position/delegation evidence. Fallback is tried when primary resolution is empty. Configured submitter fallback exists in separation checks. These mechanisms are not an accepted owner exception or a general object-scope grant. |

Direct test bodies inspected, not executed:

- [Organization tests](../../apps/organizations/tests.py):
  `test_system_admin_has_global_tenant_access_without_membership` creates a
  project through the service without a membership.
- [Project tests](../../apps/projects/tests.py):
  `test_project_list_is_tenant_scoped` verifies visible own-tenant and hidden
  foreign-tenant projects; it does not demonstrate same-tenant restricted grants.
- [Workflow tests](../../apps/workflows/test_runtime.py):
  `test_permission_and_candidacy_are_both_required` permits a position candidate
  to claim but denies completion without the domain permission; it also denies
  an owner who is not a candidate from claiming that item.
- [Workbench tests](../../apps/workflows/test_workbench.py):
  `test_tenant_isolation_permissions_and_secure_source_link` checks foreign
  subject exclusion, an own-subject link and denial without work-item view permission.

This is a bounded boundary inspection, not an endpoint-wide authorization audit.
The differing privileged behavior and claim-versus-completion checks required
narrow C2 inspection of runtime, workbench and direct test bodies. No behavior
was corrected or generalized from these findings.

## 2. Proposed scope semantics and alternatives

For ordinary business actions, require the intersection of effective user, active
tenant membership, permitted tenant lifecycle/entitlement, business permission,
object scope, domain state/data and applicable separation rules. Workflow actions
add current assignment/candidacy/delegation; they never replace any other factor.
Missing, ambiguous, expired or foreign-tenant authority denies access in the target.

| Q04 choice | Original proposed default and tradeoff | Alternative considered |
| --- | --- | --- |
| Source of scope | Membership-linked effective grants, owned by Organizations authorization; Projects owns project/site identity and hierarchy. Works without Employee/Position structures. | Effective workforce/project assignments as restrictions reduce duplicate administration but need membership mapping and a starter path without workforce. Never infer a permission from an assignment. |
| Grant combinations | Union valid explicit scopes, then intersect with tenant permissions and action-specific restrictions. Avoid implicit deny precedence and a second permission catalogue. | Deny overrides or capability-specific scope profiles require explicit precedence and conflict tests before adoption. |
| Project and site inheritance | Explicit project-wide coverage includes its sites; site-only coverage includes only that site and approved minimal parent context, not siblings or project-wide financial totals. | Enumerated site coverage avoids automatic access to new sites but needs additional administration. Acceptance must decide new-site inheritance and parent-context fields. |
| Small-Tenant access | An explicit organization-wide scope mode may cover current/future projects, still intersected with permissions and sensitive-data rules. Missing grants never silently mean unrestricted. | Enumerated projects only, with higher onboarding burden. No automatic Tenant Owner/Tenant Admin broad grant is approved. |
| Non-project and mixed-project data | Tenant-wide records need their own capability and declared scope classification; null project is not a wildcard. A whole-record mutation requires access to every affected project/site and linked sensitive source. | A domain may offer a separately designed partial read projection; never silently truncate an approval or mutation. |

The Product Owner selected A1, B1 and C1: membership-linked explicit grants union
valid scopes before intersection with all other authority; a project grant covers
all current/future sites and cannot exclude sites; partial-project access uses
explicit site grants; and delegation is bounded, time/scope-limited, revocable,
audited and non-transitive by default. Organization-wide access is explicit; role,
missing scope and null context never imply it. Reviewer names/evidence remain OPEN.

The authoritative multi-role rule adds no shortcut to that intersection. Target
authorization unions business permissions from every active applicable role
assignment on the active Membership, then intersects the result with grants,
effective project/site scope, delegation, workflow eligibility and policy. A
Membership may independently hold Tenant Owner, Tenant Admin and Project Manager;
another Membership for the same User may hold only Project Manager. Adding or
revoking one assignment changes no other assignment and records actor, Tenant,
role, timestamp and relevant reason/context. Exact schema and compatibility
cutover remain an approved-P1.1 gate, not part of this ADR preparation.

Proposed grant evidence: tenant, membership, scope kind, project and optional site,
effective interval, grantor/approver, reason, creation/revocation timestamps and
supersession history. Validate same-tenant membership/project/site and parent
consistency with database constraints where expressible and transactional service
checks. Public identifiers do not confer access. Exact schema and permission codes
belong to an approved P1.1 package, not this ADR.

Proposed lifecycle is pending review -> effective -> expired/revoked/superseded;
retain history rather than delete it. Grant/change/revoke authority is explicit,
cannot self-elevate, and cannot delegate beyond the grantor's accepted delegation
boundary. C1 prohibits self-grant, self-approval, scope expansion and permission
transfer. D1 selects explicit auditable initial Tenant Owner ownership/governance
scope at organization creation; Tenant Admin / Local Admin is a separate explicit
assignment even for the same user. Later Tenant Owners require an existing Tenant
Owner, Tenant Admin or another actor with the required user/access-management
permission and independently recorded scope/grants. Neither Tenant role alone
implies organization-wide business-data access. Exact
grantors, reviewers and implementation mechanics remain open.

## 3. Enforcement and workflow contract

Use one shared authorization policy consumed by tenant-scoped selectors, forms,
views and domain services. Filter before pagination, counts, aggregates, search,
autocomplete and export. Detail/source/document links recheck their own authority;
workbench titles, badges and audit metadata must not reveal excluded subjects.
Authorized parent navigation cannot expose sibling data or sensitive totals.
Mixed-scope reporting must label its authorized coverage; global close/posting or
reconciliation cannot silently operate on an incomplete subset. Sensitive finance,
payroll, bank and personal data still require their dedicated permissions.

These constraints carry forward the proposed access contracts in
[S04 financial authority](ADR_P0_S04_ACCOUNTING_POSTING.md),
[S05 project cost](ADR_P0_S05_BUDGET_PROJECT_COST.md) and
[S06 policy resolution](ADR_P0_S06_REGULATORY_CONTRACT_POLICY.md); project access
does not grant source drill-through, rule activation, posting or approval.

For future workflow integration:

1. Resolve subject project/site context from authoritative tenant-scoped records,
   not request fields or unvalidated stored routing hints. Validate hierarchy.
2. Intersect route results with effective membership, required permissions, object
   scope and configured separation. Preserve qualifying position/delegation
   evidence; multiple positions remain one membership/workbench identity.
3. Recheck at claim, reassign, delegate and completion as applicable. A candidate
   snapshot or existing assignment cannot preserve access after permission/scope
   revocation. Target filtering before claim is a proposed change, not a claim
   about the current claim-versus-completion behavior demonstrated above.
4. Under selected H1, filter primary candidates through current membership,
   permission, object scope, delegation, applicable separation/Self-Approval and
   all other required conditions. If none is eligible, evaluate configured
   fallback candidates through the same checks. If none remains, retain visible
   unresolved work and recover it through authorized administration. Never broaden
   access or automatically choose Tenant Owner/Tenant Admin/Platform Admin/
   Superuser/support.
5. Inside the domain transaction, lock/re-read the subject and relevant authority,
   membership and grant state, validate current scope/permission/separation, then
   atomically commit domain transition, work-item completion, next activation and
   audit. Revocation/grant changes must use a compatible locking/version protocol
   so concurrent completion cannot use stale authority; P1.1 must specify and test
   lock order and authorization linearization. Cached scope is not commit authority.

Delegation and reassignment require an eligible recipient and bounded effective
scope/time; they do not grant tenant permissions. Historical decisions retain the
membership, scope/version and qualifying routing evidence used at the time. Loss
of current access does not rewrite completed history or allow continued reading of
it. Workflow definitions remain declarative and domain services own invariants.

## 4. Privileged paths and separation: unresolved, not exceptions

| Path | Current evidence / proposed decision boundary |
| --- | --- |
| Tenant Owner / Tenant Admin — D1 | Tenant Owner and Tenant Admin / Local Admin are independent. Initial Tenant Owner ownership/governance scope is explicit at organization creation; Tenant Admin is separately assigned, and later Tenant Owner/Tenant Admin scopes/grants are independently recorded. Neither role alone grants organization-wide business-data scope or candidacy. |
| Superuser / Platform Admin — E1 | Superuser is exceptional highest technical/system authority; Platform Admin is a distinct operational platform role. They may be explicitly co-assigned but neither implies the other or ordinary Tenant business-data access. Preserve current divergent Superuser helper/runtime behavior until an approved compatibility path supplies separate scoped, authorized and audited Tenant access. |
| Support/emergency — revised F2 | Normal access requires understandable approval by an authorized tenant user plus independent platform approval. A separate emergency path may be designed only when tenant approval is practically impossible, with independent/multi-stage platform approval, recorded reason, minimum scope, short validity, full audit, actor attribution, automatic expiry/revocation and no hidden impersonation. No mechanism is implemented here. |
| Self-Approval — final G3, Revised with Protected Operations | Self-Approval is never allowed for platform-level `Protected Operations`, covering system/security/authorization/privileged-access/access-management operations; Tenant policy and Tenant Owner/Tenant Admin/Platform Admin/Superuser roles cannot override. Other financial, contractual, project, procurement, administrative and workflow approvals may support configuration. Superuser defines supported business operation types at platform level; where permitted, an explicitly authorized Tenant Owner/user may enable or disable Self-Approval for that Tenant. Tenant Owner status alone enables nothing. Platform classification changes are themselves Protected Operations. No single-user-Tenant mode; all policy changes and actual uses are audited. This explicitly revises original G1 and replaces every earlier Q04-G response. |

Product Owner selections A1/B1/C1/D1/E1, revised F2, final G3 — Revised with
Protected Operations, and H1 are recorded.
Named security/workflow and conditional domain/accounting/legal/operations/privacy
reviewers and evidence remain OPEN before this ADR can be accepted or P1.1
implemented. Final G3 — Revised with Protected Operations mandates separation while
allowing configuration for non-protected functional/business operations. Reviewers
must validate classification completeness and record misconfiguration, fraud/error-
detection, professional-validity and regulatory risks for configurable business
operations. Support
jurisdiction also depends on D03; tenant lifecycle/retention and exports retain
D05/Q03 gates. Suspended tenants
must not mutate business data and cancelled tenants must not use normal business
access in the target; special retention/export policy is separate. Current
authorization helpers require an active organization and are unchanged.

C1 self-elevation controls and F2 independent support/emergency approval fall
within final G3 Protected Operations, resolving the prior recorded precedence
tension. Exact operation classification and reviewer evidence remain open.

## 5. Compatibility and implementation acceptance gates

After ADR acceptance and separate implementation authorization:

1. Inventory each affected read/write/export and subject adapter, with its scope
   classification and privileged behavior. Resolve Q04 and role vocabulary first.
2. Expand with tenant-scoped grant/history storage and shared policy using existing
   Django/PostgreSQL and permission registry infrastructure. New capabilities need
   permission codes, registry entries, catalog/default-role migrations and tests;
   no new package or parallel authorization model is justified here.
3. Prepare a reviewed membership-by-scope backfill manifest. Existing tenant-wide
   behavior is not evidence of intended unrestricted access. Require explicit
   policy for any broad backfill and quarantine ambiguous cases for review.
4. Compare existing and proposed decisions without exposing data or changing live
   behavior. Validate pending workflow assignments/delegations and recovery before
   cutover; preserve published definitions, completed evidence and grant history.
5. Switch approved journeys coherently across selectors, direct services and
   workbench. Partial rollout must not leave an alternate unguarded entry point.
   Test revocation races, query counts and rollback. Rollback must not silently
   restore broad access after restrictions take effect; any contraction/removal
   remains separately approved.

Static design cases below are acceptance scenarios, **not executed tests**:

| Case | Proposed expected result |
| --- | --- |
| Forged tenant/session ID or foreign project/site/grant membership | Deny without names, counts or object-existence leakage. |
| Same tenant, permission for projects, grant only for project A | A visible; B excluded from lists/options/exports and denied via direct service. |
| Site A1 grant, sibling A2 and project-wide budget | A1 only; minimal parent context only under accepted field policy; deny A2 and whole-project financial action. |
| Project grant without domain permission; position or candidate alone | Deny; each factor is independently required. |
| Membership has Tenant Owner, Tenant Admin and Project Manager; one role is revoked | Union only permissions from the remaining active assignments; preserve the other roles, re-evaluate every scope/policy factor and retain revocation evidence. |
| Same User has different role sets in Tenant A and Tenant B | Resolve roles only through the active Tenant Membership; never leak or import a role from the other Tenant. |
| Eligible assignee loses grant/permission after claim | Deny completion, preserve history and recover through authorized routing. |
| Delegated actor has narrower scope or expired delegation | Deny out-of-scope/expired action; no implicit permission transfer. |
| Tenant Owner/Tenant Admin/Platform Admin/Superuser/support requests bypass | No new authority from this proposal; role assignment alone supplies no bypass and path-specific tests remain required. |
| Scope revoked concurrently with approval | Serialize authority decision with revocation; no stale-authority commit, no partial domain/work-item/audit outcome. |
| Mixed A/B record, actor sees only A; null-project sensitive record | Deny whole-record action; no null wildcard or partial approval. |
| Empty grant set, inactive membership, suspended/cancelled tenant | Deny ordinary target access as applicable; no implicit broad/default fallback. |

P1.1 acceptance additionally requires cross-project/site and cross-tenant negative
tests, list/detail/service parity, creation and relationship-change checks,
independent role add/remove and permission-union tests, per-Tenant role isolation,
role/grant lifecycle and anti-escalation audit tests, workbench/source-link leakage
checks, concurrency and representative query/performance evidence. S07 supplies
none of that runtime certification. PPC-04, P0.1 and P1.1 remain incomplete.
