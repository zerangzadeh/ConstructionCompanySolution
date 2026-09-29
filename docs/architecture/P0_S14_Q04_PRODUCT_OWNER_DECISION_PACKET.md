# P0-S14: Q04 Product Owner decision packet

**Status:** PRODUCT OWNER DECISIONS, P0-S18 FINAL ACCOUNTABLE REVIEWER DECISION
AND P0-G01 REVIEW RECORDED — no ADR accepted and no implementation authorized

**Recorded:** 2026-09-25. **Final Q04-G decision reconfirmed:** 2026-09-26.
**Role vocabulary normalized:** 2026-09-26.
**Membership-scoped multi-role rule recorded:** 2026-09-26.
**Accountable-review assignments recorded (P0-S17):** 2026-09-26 — only the
explicitly supplied reviewer assignments are recorded; the later P0-G01 review
findings are recorded below without claiming implemented-control evidence.
**Final accountable reviewer decision recorded (P0-S18):** 2026-09-26 — Azam
Zerangzadeh is assigned all Q04-A through Q04-H review responsibilities. This is
an explicit Product Owner override of the packet's reviewer-independence
expectation where applicable; it does not create an independent second human.

**P0-G01 identity-policy clarification (2026-09-27):** Azam Zerangzadeh is the
real accountable person for Platform-level review responsibilities, including
Platform Owner, Platform Admin, Superuser, Platform Security / Authorization and
Platform Operations / Privacy responsibilities. Tenant-role examples use only
clearly labelled Seed/Test identities and never constitute a real reviewer,
governance evidence or gate closure. The
[P0-G01 evidence matrix](P0_G01_Q04_ACCOUNTABLE_REVIEW_EVIDENCE_MATRIX.md) is
the authoritative preparation record for this clarification. Where a requirement
demands an independent second human, the current single-person project records an
explicit OPEN independence gap rather than inventing a person.

**P0-G01 accountable review recorded (2026-09-27):** the
[evidence matrix](P0_G01_Q04_ACCOUNTABLE_REVIEW_EVIDENCE_MATRIX.md#3-p0-g01-accountable-review-findings)
records A/B/F as `accepted with conditions` and C/D/E/G/H as `revision required`.
These are review findings about policy readiness and verified implementation gaps;
they do not accept S07 or another ADR, close P0, or authorize P1.

This packet isolates P0-S03-Q04 from the consolidated
[P0.1 ADR review packet](P0_S13_P01_ADR_REVIEW_PACKET.md). P0-S15 records the
Product Owner's explicit Q04-A through Q04-H selections and revisions for
project/site scope, privileged access, separation and workflow fallback. P0-S17
records the initially supplied reviewer assignments, and P0-S18 records the final
accountable reviewer and explicit independence override. P0-G01 records the later
bounded review findings. None accepts an ADR or authorizes P1.1, P0.2, P0.3 or any
other implementation.

The [S07 scope ADR](ADR_P0_S07_PROJECT_SITE_AUTHORIZATION.md) and current code/tests
remain authoritative for proposed and delivered behavior respectively. In
particular, current permission helpers allow an active superuser through some
business services without membership, while workflow runtime/workbench paths
require membership. That difference is compatibility evidence to disposition,
not an approved privileged-access design. No behavior changes in this packet.

## 1. Decision boundary and response rules

The target authorization contract remains an intersection: effective user,
active membership and tenant, entitlement when applicable, business permission,
object scope, valid domain state, workflow responsibility when applicable, and
configured separation. A role, position, assignment, support case or platform
credential cannot supply a missing factor.

Authoritative role vocabulary for this packet:

| Level | Role | Boundary |
| --- | --- | --- |
| Platform | Superuser | Highest exceptional technical/system authority and Protected Operations; no automatic Tenant business-data access |
| Platform | Platform Admin | Operational platform administration, Tenant provisioning and global configuration; distinct from Superuser and no automatic Tenant business-data access |
| Tenant | Tenant Owner | Highest Tenant business/policy authority; does not imply Tenant Admin |
| Tenant | Tenant Admin / Local Admin | One-Tenant administration within delegated boundaries; no global/other-Tenant authority or automatic unrestricted business-data access |
| Tenant | Tenant Manager | Business/operational management such as Project Manager or Financial Manager; no implicit Tenant/platform administration |

One user may explicitly hold multiple roles, including Platform Admin plus
Superuser or Tenant Owner plus Tenant Admin. Assignments remain independent; no
role is merged, inherited or implied by another.

Tenant/business roles are assigned in the context of `OrganizationMembership`.
The same User may therefore hold Tenant Owner, Tenant Admin and Project Manager in
one Tenant and only Project Manager in another. The authoritative target relation
is many-to-many, conceptually
`User -> Membership -> MembershipRoleAssignment -> Role`, or an equivalent model
that preserves Tenant context. Common combinations do not create composite roles;
assigning or revoking one role changes no other independent assignment.

Effective authorization unions permissions from all active applicable role
assignments, then intersects them with active Membership, explicit Grants,
effective Project/Site Scope, Delegation, Workflow eligibility and policy
constraints. Role assignment alone never implies unrestricted scope. Every role
assignment/revocation retains actor, Tenant, role, timestamp and relevant
reason/context. Current single-role membership fields remain compatibility evidence;
this packet authorizes no schema, migration, permission or runtime change.

The selections recorded below are authoritative for this decision round. Original
recommendations remain visible so revisions are not mistaken for the proposed
baseline. Formal S07 acceptance and implementation authorization remain separate
gates after accountable names, reviews and evidence are recorded.

## 2. Q04 options and recommendations

### Q04-A — source and combination of project/site grants

| Option | Tradeoff |
| --- | --- |
| **A1 — membership-linked explicit grants; union valid scopes, then intersect every other authorization factor (recommended)** | Works without workforce structures, keeps one permission catalogue and makes broad access explicit. Adds grant administration and requires careful existing-tenant backfill/review. |
| A2 — derive restrictions from effective workforce/project assignments | Reduces duplicate administration where workforce data is complete, but creates weak starter behavior, membership-mapping complexity and risk that operational assignment is mistaken for permission. Assignment must still never grant a business permission. |
| A3 — enumerated access only with no organization-wide scope mode | Maximizes explicitness but raises onboarding and maintenance cost, especially for small tenants and future projects. Missing grants still deny access. |

**Recommendation:** choose A1, including an explicit organization-wide scope mode
for authorized small-tenant administration. Organization-wide scope is a grant,
not a role implication or missing-grant default. Null project/site is never a
wildcard. Non-project and mixed-project records require declared classifications;
a whole-record action requires authority over every affected context.

**Product Owner decision (P0-S15): A1.** Use membership-linked explicit grants.
Union valid scopes, then intersect every other required authorization factor.
Organization-wide access is an explicit grant and is never inferred from a role,
missing scope, or null project/site value.

**Latest gate:** before accepting S07 or designing/implementing P1.1; before any
affected package treats tenant permission as sufficient object authority.

### Q04-B — project/site inheritance and parent context

| Option | Tradeoff |
| --- | --- |
| **B1 — project grant covers current and future child sites; site grant covers that site plus approved minimal parent context (recommended)** | Predictable project administration and safe site isolation. Requires explicit field-level definition of minimal parent context and prevents site actors from project-wide totals/actions. |
| B2 — project grant covers only sites enumerated at grant time | Avoids automatic exposure of new sites, but increases administration and can strand workflows when sites are added. |
| B3 — site grant inherits broad project access | Simpler navigation but exposes siblings, totals and sensitive project-wide records; inconsistent with least privilege and not recommended. |

**Recommendation:** choose B1. A site-only grant must not expose siblings,
project-wide financial totals, cross-site exports or whole-project mutations.
Authorized parent navigation may expose only the later approved minimal context.

**Product Owner decision (P0-S15): B1.** A project grant covers all current and
future sites belonging to that project and does not support site exclusions. A
site grant covers only that site plus the minimum approved parent context. Partial
project access therefore uses explicit site grants, not a project grant.

**Latest gate:** with Q04-A before S07 acceptance/P1.1 design; each consuming
domain must classify parent fields before its scoped UI/service acceptance.

### Q04-C — grant administration, delegation and reassignment

| Option | Tradeoff |
| --- | --- |
| **C1 — delegated administration is explicit, bounded and non-transitive by default (recommended)** | Prevents self-elevation and uncontrolled re-delegation; needs an explicit grantor boundary, approver, interval and recovery route. |
| C2 — allow transitive delegation within the recipient's current scope | More flexible for large tenants but complicates provenance, revocation and maximum-authority checks; requires depth/precedence rules and stronger audit. |
| C3 — Tenant Owner-only grant administration | Simple authority story but creates availability bottlenecks and conflicts with optional enterprise delegation. |

**Recommendation:** choose C1. A grantor may only propose within authority they are
explicitly allowed to administer; the recipient must independently hold required
business permissions. No self-grant, self-approval, scope expansion or permission
transfer is allowed. Delegation/reassignment must be time- and scope-bounded,
rechecked at claim/action/completion, immediately affected by revocation, and
retain grantor, approver, reason and qualifying evidence. Any future re-delegation
must be a separately selected policy, not an implication of delegation.

**Product Owner decision (P0-S15): C1.** Delegated administration is explicit,
bounded, time- and scope-limited, auditable, revocable and non-transitive by
default. Self-grant, self-approval, scope expansion and permission transfer are
prohibited. Recheck eligibility and authority at relevant claim, reassignment,
delegation, action and completion points.

**Latest gate:** before S07 acceptance/P1.1 implementation and before pending
workflow assignments can be migrated or cut over to scope enforcement.

### Q04-D — Tenant Owner and Tenant Admin / Local Admin scope/bootstrap

| Option | Tradeoff |
| --- | --- |
| **D1 — explicit grants for ordinary business access; atomic, auditable initial Tenant Owner bootstrap; separately assigned Tenant Admin administration (recommended)** | Preserves usable Tenant creation without merging ownership and administration or making role labels permanent bypasses. Requires explicit bootstrap scope and later review/revocation rules. |
| D2 — role-implied organization-wide business scope for every Tenant Owner/Tenant Admin | Low administration but makes role assignment a broad data-access elevation, weakens least privilege and obscures scope history. |
| D3 — no bootstrap or broad mode; enumerate all scopes immediately | Strict but can leave a new tenant unable to administer itself and creates high setup burden. |

**Recommendation:** choose D1. Organization creation should establish the initial
Tenant Owner membership and its explicit ownership/governance scope atomically and
audibly; this is a proposed P1.1 requirement, not delivered schema or authority.
Tenant Admin / Local Admin privileges are a separate explicit role assignment,
even when assigned to the same user. Additional Tenant Owner and Tenant Admin
memberships receive only explicitly approved scope. Grant administration requires
the dedicated capability and cannot be inferred from either role.

**Product Owner decision (P0-S15), normalized to the authoritative role model:
D1.** Create the initial Tenant Owner and its required ownership/governance scope
explicitly and audibly with the organization. Any Tenant Admin / Local Admin role
for that user is assigned separately. An existing Tenant Owner, Tenant Admin or
another Tenant user holding the required user/access-management permission may
create a subsequent Tenant Owner only within accepted authority; that Owner's
scope and grants are independently assigned and recorded. Tenant Owner role alone
never implies Tenant Admin privileges or organization-wide business-data access.
Adding or removing the Tenant Owner assignment neither adds nor removes Tenant
Admin, Tenant Manager, Project Manager or any other independent assignment.

**Latest gate:** before accepting S07, canonical role/backfill design or P1.1
implementation. Exact bootstrap/backfill mechanics require a separately approved
implementation package.

### Q04-E — Superuser and Platform Admin access

| Option | Tradeoff |
| --- | --- |
| **E1 — exclude superuser status from ordinary business authority; use separately authorized, narrow control/diagnostic paths (recommended)** | Removes an implicit cross-tenant business bypass and keeps platform operations distinct. Requires inventory and compatible transition of current helper behavior. |
| E2 — retain a general superuser business bypass | Operationally convenient but conflicts with active-membership/object-scope evidence, broadens breach impact and makes workflow behavior inconsistent. Not recommended. |
| E3 — require ordinary tenant membership/grants for every platform operation | Strong consistency but may not support recovery/diagnostic duties when tenant access is unavailable; control-plane needs remain unresolved. |

**Recommendation:** choose E1. Superuser alone should grant no ordinary tenant
read, mutation, approval, export or workflow action. Any future platform control
path must be operation-specific, independently authorized, minimally scoped and
audited, and must not become background authority. Current divergent helpers stay
unchanged until an approved compatibility/cutover package exists.

**Latest gate:** policy choice before S07 acceptance/P1.1 design; path-by-path
inventory, migration and rollback acceptance before changing current behavior.
D03/D04 still govern operator location and recovery duties.

**Product Owner decision (P0-S15): E1, normalized to the authoritative role
model.** Superuser status alone supplies no ordinary Tenant business-data access.
A Superuser is the exceptional highest technical/system authority. Platform Admin
is a separate operational platform role for provisioning, global configuration and
permitted platform administration; it also supplies no automatic Tenant business-
data access. One user may explicitly hold both roles, but neither implies the
other. Any future Tenant-data access requires a separate explicit, scoped,
authorized and auditable mechanism and is never inferred from either role.

### Q04-F — support and emergency access

| Option | Tradeoff |
| --- | --- |
| F1 — no tenant business-data access; tenant supplies minimized/redacted diagnostics | Strongest isolation and simplest authority model, but may lengthen diagnosis and recovery. |
| **F2 — no standing access; allow a separately approved tenant-authorized, purpose/scope/time-limited grant when necessary (recommended)** | Balances supportability and tenant control. Adds consent, independent approval, expiry/revocation, jurisdiction, audit and per-action enforcement obligations. |
| F3 — standing support or emergency impersonation | Fastest intervention but creates broad concealed authority and unacceptable escalation/audit risk. Not recommended. |

**Recommendation:** choose F2 with F1 as the default operating state. A support
case, plan tier, database credential or emergency label supplies no authorization.
Each grant requires verified operator and tenant context, explicit purpose/actions,
project/site/data scope, independent approval, effective interval, visible original
actor attribution and immediate revocation. It grants no business approval,
financial/workflow mutation, export or re-grant authority unless that exact action
is separately accepted. No shared credentials or concealed impersonation.

**Latest gate:** policy before S07 acceptance and affected S11/P0.3 support-control
acceptance. D03 must decide support jurisdictions/operators and Q03 must decide
audit/consent retention and export visibility before enabling the path. No support
mechanism is authorized by selecting F2.

**Product Owner decision (P0-S15): F2 — REVISED.** Normal support access requires
simple approval by an authorized tenant user and independent platform approval.
The tenant-facing request must explain purpose, requested scope, allowed actions
and duration without requiring technical expertise. Access is purpose-, scope-
and time-limited, revocable, attributable and fully audited.

When tenant approval is practically impossible during a genuine emergency, a
separate highly restricted path may be designed. It requires multi-stage or
independent platform approval, recorded emergency reason, minimum necessary
scope, short explicit validity, complete audit, original actor attribution,
automatic expiry/revocation and no hidden impersonation. This emergency path is
an explicit revision to the original F2 recommendation; it is policy direction,
not an implemented or authorized access mechanism.

### Q04-G — maker-checker separation and small-tenant fallback

| Option | Tradeoff |
| --- | --- |
| **G1 — mandatory separation for protected actions; configurable documented fallback only for explicitly classified lower-risk actions (recommended)** | Preserves independent control where required while permitting a viable small-tenant profile. Requires every package to classify actions and specify fallback evidence. |
| G2 — mandatory separation for every approval | Strongest uniform rule but can make small tenants unable to complete low-risk work and may force artificial users. |
| G3 — configurable self-approval for all actions | Flexible but can defeat statutory, financial, security and independent-verification controls. Not recommended. |

**Recommendation:** choose G1. At minimum, prohibit self-grant/elevation/support
approval; same-actor prepare-and-post/release/reverse of financial value; period
close/reopen; payroll finalization/payment; regulatory rule activation; destructive
retention/hold release; and any legally or contractually independent verification.
Each downstream ADR/package may add protected combinations. For a lower-risk action,
fallback is valid only when policy explicitly permits it, no other eligible actor
exists, the actor has every ordinary permission/scope requirement, a reason and
risk acknowledgement are retained, and the result is visibly auditable. Tenant
Owner status never overrides a protected combination.

**Latest gate:** the Q04 baseline before S07 acceptance; domain-specific matrices
before accepting S04-S06 or enabling any affected downstream workflow.

**Final and authoritative Product Owner decision (reconfirmed 2026-09-26):
G3 — Revised with Protected Operations.** This explicitly revises and replaces
the original G1 recommendation and every earlier Q04-G response. Define a platform-level
`Protected Operations` category covering system, security, authorization,
privileged-access and access-management operations where Self-Approval could
elevate the actor's authority or bypass a security control. Self-Approval is never
allowed for Protected Operations. Tenant configuration cannot override that
restriction, and Tenant Owner, Tenant Admin, Platform Admin or Superuser role
assignment supplies no bypass.

Protected Operations include at minimum: self-granting permissions; increasing
one's own access; assigning/approving one's own privileged role; creating and
approving one's own support or emergency access; changing and self-approving an
authorization/security policy; weakening and self-approving an audit/security
control; and any equivalent system-level self-elevation or security-control bypass.

All non-protected functional/business operation types may support configurable
Self-Approval, including financial, contractual, project, procurement,
administrative and workflow approvals. They are not automatically self-approvable.
Superuser defines at platform level which business operation types support
Self-Approval. That classification changes
authorization policy and is therefore a Protected Operation under the normalized
role model; ordinary Platform Admin global-configuration authority does not imply
this Superuser capability. Where platform policy permits Self-Approval, the Tenant
Owner or another Tenant user with the explicit policy-management permission may
enable or disable it according to that Tenant's policy. Tenant Owner status alone
does not enable Self-Approval. No special single-user-Tenant mode or Tenant
classification is introduced.

Every policy/configuration change records actor, date/time, Tenant where applicable,
operation type, previous value, new value and required reason/context. Every actual
use of Self-Approval is also auditable. Tenant enablement remains subject to its internal
controls, contracts, accounting, audit, legal and regulatory obligations; platform
capability is not evidence of suitability for every tenant.

**Recorded risk/tradeoff:** the final revision resolves the earlier C1/F2-versus-
G3 tension by making self-elevation, support/emergency self-approval and security-
control bypass Protected Operations. Functional/business Self-Approval still
creates fraud/error-detection, professional-validity and regulatory risk when
enabled. Named security, workflow, accounting/control, legal/compliance where
applicable and affected-domain reviewers must assess classification completeness,
tenant controls, audit evidence and release implications without replacing the
Product Owner decision.

### Q04-H — workflow route fallback and unresolved work

| Option | Tradeoff |
| --- | --- |
| **H1 — evaluate fallback after primary candidates are filtered for current eligibility; fallback candidates pass the same checks (recommended)** | Prevents work being assigned to actors who cannot legally act and gives deterministic recovery. Requires eligibility rechecks and an unresolved-work administration path. |
| H2 — fallback only when the raw primary route is empty | Preserves route intent but strands work when named candidates exist yet lack current permission/scope/separation eligibility. |
| H3 — automatically route unresolved work to Tenant Owner/Tenant Admin/support | Reduces queue blockage but creates an implicit privileged bypass and conflicts with scope/SoD. Not recommended. |

**Recommendation:** choose H1. Filter route results by active membership, required
permission, effective object scope, delegation and separation before deciding the
primary set is usable. Apply the same checks to configured fallback. If no eligible
actor remains, retain a visible unresolved work item and recover it through an
authorized administrative action; never auto-select Tenant Owner/Tenant Admin/Superuser/support
or relax separation. Recheck on claim, reassign, delegate and completion. Completed
history retains the qualifying authority evidence.

**Latest gate:** before S07 acceptance/P1.1 workflow integration and before any
new or changed workflow definition relying on fallback is accepted for publication.

**Product Owner decision (P0-S15): H1.** Treat a primary route as usable only after
current eligibility checks, including membership, permission, scope, delegation,
applicable separation/Self-Approval policy and every other required condition.
Apply the same checks to configured fallback candidates. If none is eligible,
retain visible unresolved work; never auto-route it to Tenant Owner, Tenant Admin,
Platform Admin, Superuser or support. Recheck at relevant claim, reassignment,
delegation, action and completion.

## 3. Accountable review requirements

The packet names people only where the Product Owner supplied an explicit
responsibility-to-Q04 assignment. Team names, job titles alone, or an unassigned
future owner do not close a gate.

| Review responsibility | Minimum evidence required | Required for |
| --- | --- | --- |
| Product Owner decision | Explicit A-H selections or requested revisions; acknowledgement of tradeoffs and downstream gates | Every Q04 choice |
| Security/authorization reviewer | Threat review of cross-tenant/same-tenant leakage, anti-escalation, privileged paths, revocation races, audit and compatibility transition | A-F and H; S07 acceptance |
| Workflow/control reviewer | Review of candidacy, delegation/reassignment, eligible-route fallback, unresolved-work recovery, atomic recheck and historical evidence | C, G and H; S07 workflow clauses |
| Accounting/control reviewer | Review business-operation Self-Approval risks, tenant controls, audit evidence and financial/project-control implications; Protected Operations remain mandatory | G; affected S04-S06 acceptance |
| Operations/privacy reviewer | Support identity, consent, minimization, jurisdiction, audit visibility, expiry/revocation and incident interaction | E-F; with D03/Q03 before support enablement |
| Affected domain owner | Action-by-action scope classification, parent-context fields and domain-specific SoD/fallback additions | Before each consuming package's design acceptance |
| Legal/compliance reviewer, where applicable | Review configured Self-Approval and emergency access against external independence, statutory, contractual and evidence obligations; record unresolved release constraints | F-G for regulated or contractually controlled operations |

For P0-G01, the real accountable reviewer named for each Platform-level
responsibility is Azam Zerangzadeh under the 2026-09-27 identity policy. A
Tenant Owner, Tenant Admin, approver or workflow actor appearing in a test case
must use the named Seed/Test identity in the P0-G01 matrix. Such an identity is
test data only: it cannot be substituted for a reviewer, approval, evidence or
independent challenge.

The packet originally required the Product Owner to record why independence is not
defeated when one person holds more than one review responsibility, and prohibited
the decision maker from being the sole reviewer of their own privileged access.
P0-S18 explicitly overrides that reviewer-independence expectation where
applicable by assigning one final accountable reviewer across all Q04 review
responsibilities. Review evidence must still identify version, date, unresolved
objections and resulting revisions; it is not ADR acceptance or implementation
authorization by itself.

**Recorded conflict and risk:** the P0-S18 decision conflicts with the packet's
independent-challenge expectation and concentrates security/authorization,
workflow/control, accounting/control, operations/privacy, affected-domain and
conditional legal/compliance review accountability in one person. This reduces
separation and independent challenge, creates key-person and confirmation-bias
risk, and does not itself demonstrate specialist competence or satisfy any
external professional, statutory or contractual independence requirement. The
Product Owner decision remains authoritative for this packet and is not replaced
or rejected; these risks remain explicit review and release constraints until
supported by supplied evidence or a later explicit Product Owner revision.

P0-S18 records Azam Zerangzadeh as the final accountable reviewer for every
required responsibility across Q04-A through Q04-H. The following table is the
**historical P0-S19 pre-review register**: it recorded no supplied review fact at
that time, so its fields were `OPEN`. The current P0-G01 findings, evidence
references, dates, objections and conditions are authoritative in the
[P0-G01 evidence matrix](P0_G01_Q04_ACCOUNTABLE_REVIEW_EVIDENCE_MATRIX.md#3-p0-g01-accountable-review-findings).

| Choice | Required reviewer responsibilities | Reviewer names | Review outcomes | Evidence/version and review dates | Unresolved objections | Resulting revisions from reviewer feedback |
| --- | --- | --- | --- | --- | --- | --- |
| Q04-A | Security/authorization; affected domain owner | Azam Zerangzadeh — all required responsibilities | OPEN | OPEN | OPEN | OPEN |
| Q04-B | Security/authorization; affected domain owner | Azam Zerangzadeh — all required responsibilities | OPEN | OPEN | OPEN | OPEN |
| Q04-C | Security/authorization; workflow/control | Security / Authorization Reviewer — Azam Zerangzadeh; Workflow / Control Reviewer — Azam Zerangzadeh | OPEN | OPEN | OPEN | OPEN |
| Q04-D | Security/authorization; affected tenant/access domain owner | Azam Zerangzadeh — all required responsibilities | OPEN | OPEN | OPEN | OPEN |
| Q04-E | Security/authorization; operations/privacy | Security / Authorization Reviewer — Azam Zerangzadeh; Operations / Privacy Reviewer — Azam Zerangzadeh | OPEN | OPEN | OPEN | OPEN |
| Q04-F revised | Security/authorization; operations/privacy; legal/compliance where applicable | Azam Zerangzadeh — all required responsibilities, including legal/compliance where applicable | OPEN | OPEN | OPEN | OPEN |
| Q04-G final revision | Security/authorization; workflow/control; accounting/control and legal/compliance where applicable; affected domain owner | Azam Zerangzadeh — all required responsibilities, including legal/compliance where applicable | OPEN | OPEN | OPEN | OPEN |
| Q04-H | Security/authorization; workflow/control; affected domain owner | Azam Zerangzadeh — all required responsibilities | OPEN | OPEN | OPEN | OPEN |

## 4. Affected ADRs and latest gates

| ADR / scope | Q04 effect | Latest decision gate retained |
| --- | --- | --- |
| [S07 Project/site authorization](ADR_P0_S07_PROJECT_SITE_AUTHORIZATION.md) | Primary owner of A-H; scope, privilege, separation and workflow contract | A-H are selected; named security/workflow and conditional specialist review remains required before formal S07 acceptance or P1.1 implementation |
| [S04 Accounting/posting](ADR_P0_S04_ACCOUNTING_POSTING.md) | Object scope; privileged financial actions; prepare/approve/post/reverse and close/reopen separation | Q04 baseline plus named accounting/control review before affected S04 formal acceptance; P1.1 remains a P2/P3 prerequisite |
| [S05 Budget/project cost](ADR_P0_S05_BUDGET_PROJECT_COST.md) | Project/site reads, acceptance/rebaseline, classifications, forecasts and exports | Q04 baseline plus protected budget/control combinations before affected S05/P4.1 design acceptance |
| [S06 Regulatory/contract policy](ADR_P0_S06_REGULATORY_CONTRACT_POLICY.md) | Rule/term administration, activation and scoped consumption | Q04 privilege/separation baseline before affected S06/P1.2/P6.3 acceptance; Q02 professional gates remain |
| [S08 Private storage](ADR_P0_S08_PRIVATE_DOCUMENT_STORAGE.md) | Linked-context reads/downloads/exports and privileged/support access to bytes | A-F baseline before affected storage/DMS design acceptance; D03/D05/Q03 and storage choices remain open |
| [S09 DMS links](ADR_P0_S09_DMS_DOMAIN_LINKS.md) | Every linked context participates in access; no support/adapter bypass | A-H as applicable before P1.3 link access/cutover acceptance; S09 ownership/migration and Q03 remain open |
| [S10 Async/outbox](ADR_P0_S10_ASYNC_OUTBOX_IDEMPOTENCY.md) | Workers/transport do not inherit authority; delayed work rechecks operation-specific scope | E-H before enabling affected background operations; D03-D05/Q03 and first-operation/dependency choices remain open |
| [S11 Tenant lifecycle/support](ADR_P0_S11_TENANT_LIFECYCLE_ENTITLEMENTS_SUPPORT.md) | Tenant Owner/Platform Admin/Superuser split, inactive-Tenant paths, support grants and no background exception | D-F/G as applicable before affected support/lifecycle controls; D03-D05/Q03 and operation-specific authority remain open |
| [S12 Future-network privacy](ADR_P0_S12_FUTURE_NETWORK_PRIVACY.md) | Publication/consent/support state grants no tenant membership or scope | Q04 baseline constrains any future design; network trigger, privacy/legal/security/competition/operations gates remain open |

Completing the remaining Q04 reviews would remove only this shared policy blocker.
It does not accept any ADR,
resolve Q01-Q03 or D03-D05, freeze the release contract, complete P0/P0.1/PPC-04,
or authorize a migration, permission, dependency, privileged mechanism, background
operation, P1.1, P0.2 or P0.3.

## 5. Product Owner response record

Selections, rationale and the explicit P0-S18 final accountable reviewer decision
are recorded. The table below is the historical Product Owner selection record;
the later review outcomes and evidence findings are recorded in the
[P0-G01 evidence matrix](P0_G01_Q04_ACCOUNTABLE_REVIEW_EVIDENCE_MATRIX.md#3-p0-g01-accountable-review-findings).

| Choice | Selected option / revision | Product Owner rationale | Required reviewer name(s) | Review outcome/evidence |
| --- | --- | --- | --- | --- |
| Q04-A grants | A1 | Explicit grants prevent role, missing-scope and null-context inference while retaining unioned authorized coverage. | Azam Zerangzadeh — all required responsibilities | OPEN |
| Q04-B inheritance | B1 | Project access covers all its sites; partial-project access uses explicit site grants and minimal parent context. | Azam Zerangzadeh — all required responsibilities | OPEN |
| Q04-C delegation | C1 | Bounded, revocable, non-transitive administration prevents self-elevation and permission transfer while preserving controlled delegation. | Security / Authorization Reviewer — Azam Zerangzadeh; Workflow / Control Reviewer — Azam Zerangzadeh | OPEN |
| Q04-D Tenant Owner / Tenant Admin | D1 | Explicit initial Tenant Owner bootstrap preserves Tenant operability; Tenant Admin is separately assigned and neither role implies broad business-data access. | Azam Zerangzadeh — all required responsibilities | OPEN |
| Q04-E Superuser / Platform Admin | E1 | The independent platform roles remain control-plane authorities; neither implies the other or ordinary Tenant business-data authority. | Security / Authorization Reviewer — Azam Zerangzadeh; Operations / Privacy Reviewer — Azam Zerangzadeh | OPEN |
| Q04-F support/emergency | F2 — REVISED | Dual-approved normal access balances tenant understanding and platform control; a separately controlled emergency route covers genuine inability to obtain tenant approval. | Azam Zerangzadeh — all required responsibilities, including legal/compliance where applicable | OPEN |
| Q04-G maker-checker | G3 — Revised with Protected Operations; final; replaces every earlier Q04-G response and explicitly revises original G1 recommendation | Self-Approval is never allowed for Protected Operations; other business operations may be enabled by Superuser platform policy and then by authorized Tenant policy, with full audit and no special single-user-Tenant mode. | Azam Zerangzadeh — all required responsibilities, including legal/compliance where applicable | OPEN |
| Q04-H workflow fallback | H1 | Eligibility-filtered primary and fallback routing prevents privileged-role bypass and preserves recoverable unresolved work. | Azam Zerangzadeh — all required responsibilities | OPEN |

The record preserves the rejected G1 recommendation, revised F2/G3 choices and
compatibility concerns. Any later change must be explicit; reviewer feedback is
not itself a replacement Product Owner decision.

## 6. Acceptance boundary and next bounded handoff

P0-S14 packet preparation is complete, P0-S15 records the Product Owner selections,
and P0-S16 records that accountable reviews were pending. P0-S17 records the
initial assignments, and P0-S18 records Azam Zerangzadeh as final accountable
reviewer for all Q04 review responsibilities together with the explicit Product
Owner independence override. P0-S19 is historical pre-review evidence only.
P0-G01 records the current review outcomes: A/B/F are `accepted with conditions`;
C/D/E/G/H are `revision required`. The Q04 accountable-review gate remains
**OPEN** because no ADR is accepted and the recorded remediation, implementation,
compliance and independence conditions remain unresolved. Reviewer assignment and
the independence override are not approval. The recorded concentration and
external-independence risks remain explicit.

The next bounded handoff is submission of actual review outcomes and evidence for
each decision, with particular attention to the recorded concentration risk,
revised F2 emergency access, and final G3 — Revised with Protected Operations
classification and business Self-Approval risk. A separately authorized session
may record only the supplied reviews and update affected proposal statuses.
It must preserve current behavior and must not accept an ADR or start
P1.1/P0.2/P0.3 implementation unless that authority is separately and explicitly
supplied after the applicable gates are met.
