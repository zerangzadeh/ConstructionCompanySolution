# P0-G01 Q04 accountable-review evidence matrix

**Status:** P0-G01 REVIEW RECORDED — no ADR is accepted and no P1
implementation is authorized. The review distinguishes approved policy, verified
current implementation, proposed behavior and missing evidence.

**Recorded/reviewed:** 2026-09-27. **Accountable reviewer:** Azam Zerangzadeh
(Platform-level responsibilities). **Purpose:** define and record the bounded
`P0-G01` accountable review without repeating empty `OPEN` fields. It applies the
Platform/Tenant identity policy supplied for the remaining P0 review work and
uses the final Product Owner decisions in
[the Q04 decision packet](P0_S14_Q04_PRODUCT_OWNER_DECISION_PACKET.md).

## 1. Identity policy and evidence rules

- **Azam Zerangzadeh** is the real accountable person for every Platform-level
  review responsibility shown below: Platform Owner, Platform Admin, Superuser,
  Platform Security / Authorization, Platform Operations / Privacy, and any
  other Platform-level review responsibility.
- The following are **Seed/Test identities only**, used if a review artefact needs
  a concrete Tenant actor: `tenant-owner-seed`, `tenant-admin-seed`,
  `tenant-manager-seed`, `tenant-approver-seed`, `tenant-user-seed` and
  `tenant-workflow-actor-seed`. They are not real people, accountable reviewers,
  evidence approvers or governance-gate evidence.
- An actual review record must provide an outcome, immutable/retrievable evidence
  reference and version, real review date, objections and resulting revisions for
  each item. A policy decision, reviewer assignment, test identity or this matrix
  is not review evidence.
- No independent second human is invented. The same-person Product Owner and
  Platform reviewer arrangement is an **OPEN independence/challenge gap**. If a
  statutory, contractual, professional or customer requirement calls for an
  independent second human, that requirement remains OPEN until actual independent
  evidence is supplied.
- `OPEN` means no actual evidence was supplied. It is retained rather than
  inferred, even when Azam Zerangzadeh is the accountable Platform reviewer.

## 2. Evidence-intake matrix

| Q04 item | Final Product Owner decision | Required reviewer responsibility | Accountable real reviewer | Tenant scenario identity, if needed | Required review outcome | Required evidence/document/version | Required review date | Unresolved objections | Resulting revisions | Independence requirement / governance gap |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Q04-A — grants | **A1:** membership-linked explicit grants; union valid scopes, then intersect all other authorization factors; organization-wide scope only as an explicit grant | Platform Security / Authorization; Platform affected-domain ownership for scope classification | Azam Zerangzadeh | `tenant-admin-seed` grant administrator; `tenant-user-seed` recipient | **OPEN** — explicit disposition on cross-Tenant/project/site leakage, null/missing-scope denial, grant union and revocation | **OPEN** — versioned threat/authorization review with scope-classification inventory and negative-case results | **OPEN** | **OPEN** | **OPEN** | **OPEN** — same-person independent-challenge gap; no second human invented |
| Q04-B — inheritance | **B1:** project grant covers all current/future sites; site grant covers only that site plus approved minimal parent context | Platform Security / Authorization; Platform affected-domain ownership for parent-field classification | Azam Zerangzadeh | `tenant-user-seed` with project grant; `tenant-user-seed` with site-only grant | **OPEN** — explicit disposition on site sibling isolation, parent-context minimum and whole-project action denial | **OPEN** — versioned parent-field classification and project/site negative-case review | **OPEN** | **OPEN** | **OPEN** | **OPEN** — same-person independent-challenge gap; no second human invented |
| Q04-C — delegation | **C1:** explicit, bounded, time/scope-limited, auditable, revocable and non-transitive delegation; prohibit self-grant, self-approval, scope expansion and permission transfer | Platform Security / Authorization; Platform Workflow / Control | Azam Zerangzadeh | `tenant-admin-seed` grantor; `tenant-user-seed` recipient; `tenant-workflow-actor-seed` assignee | **OPEN** — explicit disposition on anti-escalation, revocation, recheck points, delegation provenance and unresolved recovery | **OPEN** — versioned delegation/control review with claim, reassignment, expiry and revocation cases | **OPEN** | **OPEN** | **OPEN** | **OPEN** — same-person independent-challenge gap; no second human invented |
| Q04-D — Tenant bootstrap | **D1:** atomic/auditable initial Tenant Owner membership and explicit ownership/governance scope; Tenant Admin is separately assigned; neither role implies broad business-data scope | Platform Security / Authorization; Platform tenant/access-domain ownership | Azam Zerangzadeh | `tenant-owner-seed`; `tenant-admin-seed`; `tenant-manager-seed` | **OPEN** — explicit disposition on atomic bootstrap, independent assignments, backfill and final-owner protection | **OPEN** — versioned bootstrap/backfill/rollback design review and Seed/Test scenario results | **OPEN** | **OPEN** | **OPEN** | **OPEN** — same-person independent-challenge gap; no second human invented |
| Q04-E — platform access | **E1:** Superuser and Platform Admin are independent Platform roles; neither supplies ordinary Tenant business-data access; any future access is separately scoped, authorized and audited | Platform Security / Authorization; Platform Operations / Privacy | Azam Zerangzadeh | `tenant-user-seed` only for denied-access scenarios | **OPEN** — explicit disposition on privileged-path inventory, no-bypass transition, diagnostic/control-path minimum scope and audit | **OPEN** — versioned privileged-path inventory, compatibility/cutover review and denied-access evidence | **OPEN** | **OPEN** | **OPEN** | **OPEN** — same-person independent-challenge gap; external operational/privacy independence remains OPEN if required |
| Q04-F — support/emergency | **F2 — Revised:** no standing access; normal access requires authorized Tenant approval plus independent Platform approval; emergency path is separately controlled, minimum-scope, short-lived and auditable | Platform Security / Authorization; Platform Operations / Privacy; Platform legal/compliance assessment where a legal, contractual or regulatory obligation applies | Azam Zerangzadeh for Platform responsibilities | `tenant-approver-seed`; `tenant-user-seed` support subject | **OPEN** — explicit disposition on consent, operator identity, purpose/scope/time, emergency threshold, expiry/revocation, original-actor audit and export/retention constraints | **OPEN** — versioned support/emergency control review; evidence of D03/Q03 dependency analysis; legal/compliance artefact where applicable | **OPEN** | **OPEN** | **OPEN** | **OPEN** — same-person challenge gap; independent Platform approval is a target control and must be proven by a real independent human when implemented; external legal/compliance independence remains OPEN where applicable |
| Q04-G — maker-checker | **G3 — Revised with Protected Operations:** Self-Approval is prohibited for Protected Operations; selected non-protected business operations may support platform-then-Tenant configuration with audit and no single-user-Tenant exception | Platform Security / Authorization; Platform Workflow / Control; Platform Accounting / Control; Platform legal/compliance assessment where applicable; Platform affected-domain ownership | Azam Zerangzadeh for Platform responsibilities | `tenant-owner-seed`; `tenant-approver-seed`; `tenant-workflow-actor-seed` | **OPEN** — explicit disposition on Protected-Operations completeness, policy-change protection, business Self-Approval classification, financial/control risk and audit evidence | **OPEN** — versioned Protected-Operations catalogue, operation-classification matrix, maker-checker/control review and legal/compliance artefact where applicable | **OPEN** | **OPEN** | **OPEN** | **OPEN** — same-person challenge gap; accounting/control and legal/compliance independent review remains OPEN whenever an external requirement demands it |
| Q04-H — workflow fallback | **H1:** filter primary and fallback candidates by current eligibility; retain visible unresolved work when none are eligible; never auto-route to privileged/support roles or relax separation | Platform Security / Authorization; Platform Workflow / Control; Platform affected-domain ownership | Azam Zerangzadeh | `tenant-workflow-actor-seed`; `tenant-approver-seed`; `tenant-admin-seed` for authorized recovery | **OPEN** — explicit disposition on eligibility filtering, unresolved-work visibility/recovery, claim/reassign/delegate/complete rechecks and history | **OPEN** — versioned routing/fallback review with ineligible-primary, ineligible-fallback and unresolved-work cases | **OPEN** | **OPEN** | **OPEN** | **OPEN** — same-person independent-challenge gap; no second human invented |

## 3. P0-G01 accountable-review findings

The review evidence is this 2026-09-27 matrix together with the cited current
repository paths and authoritative records. Source/test bodies were reviewed;
the focused test run could not create `test_construction_erp` because it already
existed and was in use. It is therefore **not** passing-test evidence.

| Q04 | Decision | Outcome | Exact evidence / stable reference | Review date | Unresolved objections | Resulting revisions or conditions | Remaining dependencies | External independence status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | A1 | **accepted with conditions** | [Q04 packet A1](P0_S14_Q04_PRODUCT_OWNER_DECISION_PACKET.md#q04-a--source-and-combination-of-projectsite-grants); [S07 scope semantics](ADR_P0_S07_PROJECT_SITE_AUTHORIZATION.md#2-proposed-scope-semantics-and-alternatives); current one-role membership: `apps/organizations/models.py::OrganizationMembership`; tenant permission/superuser path: `apps/organizations/authorization.py::{get_active_membership,has_business_permission,require_business_permission}`; target gap confirmed by `PRODUCT_CAPABILITY_AND_READINESS_AUDIT.md` Authorization row | 2026-09-27 | No current explicit project/site grant, effective-scope or multi-role model exists; tenant permission remains insufficient for A1 | No change to A1. Add P1.1 grant/scope, multi-role migration, revocation and cross-tenant/project negative-test acceptance conditions | Accepted S07; P1.1 design/package authority; scope-classification inventory; migration/backfill/rollback | **OPEN:** same-person independent-challenge gap. No external independence rule was evidenced for A1. |
| B | B1 | **accepted with conditions** | [Q04 packet B1](P0_S14_Q04_PRODUCT_OWNER_DECISION_PACKET.md#q04-b--projectsite-inheritance-and-parent-context); [S07 parent/scope rule](ADR_P0_S07_PROJECT_SITE_AUTHORIZATION.md#2-proposed-scope-semantics-and-alternatives); current project/site authorization absence: `PRODUCT_CAPABILITY_AND_READINESS_AUDIT.md` Authorization row | 2026-09-27 | Minimal parent-context fields and each consuming-domain classification are not yet approved or implemented | No change to B1. Require a versioned parent-field classification, site-sibling denial and whole-project-action checks before consuming UI/service acceptance | A1/S07 acceptance; P1.1 scope selectors/query enforcement; domain classification inventory | **OPEN:** same-person independent-challenge gap. No external independence rule was evidenced for B1. |
| C | C1 | **revision required** | [Q04 packet C1](P0_S14_Q04_PRODUCT_OWNER_DECISION_PACKET.md#q04-c--grant-administration-delegation-and-reassignment); [S07 enforcement contract](ADR_P0_S07_PROJECT_SITE_AUTHORIZATION.md#3-enforcement-and-workflow-contract); current delegation resolution: `apps/workflows/routing.py::{_apply_delegations,resolve_step_candidates}`; creation/revocation: `apps/workflows/runtime.py::{create_workflow_delegation,revoke_workflow_delegation}`; current scenarios: `apps/workflows/test_runtime.py::WorkflowRuntimeTests::{test_effective_delegation_adds_only_current_delegate,test_claim_release_reassign_history_and_immutability}` | 2026-09-27 | Current delegation checks active interval, revocation, tenant and a generic context match, but does not establish C1's grantor-authority boundary, object-scope administration, recipient permission proof, non-escalation or required action-time rechecks; reassignment can create an explicit candidate without target-policy scope validation | Preserve C1; revise the S07/P1.1 implementation contract to enumerate delegation/reassignment authority, recipient eligibility, expiry/revocation races, audit evidence and denial tests | A/B/D scope model; accepted S07; P1.1 service/migration/test package; workflow compatibility/cutover review | **OPEN:** same-person independent-challenge gap. No external independence rule was evidenced for C1. |
| D | D1 | **revision required** | [Q04 packet D1](P0_S14_Q04_PRODUCT_OWNER_DECISION_PACKET.md#q04-d--tenant-owner-and-tenant-admin--local-admin-scopebootstrap); [S07 compatibility gates](ADR_P0_S07_PROJECT_SITE_AUTHORIZATION.md#5-compatibility-and-implementation-acceptance-gates); current single role: `apps/organizations/models.py::OrganizationMembership`; current bootstrap: `apps/organizations/services.py::create_organization_with_owner`; current role replacement: `apps/organizations/services.py::update_organization_membership`; evidence test: `apps/organizations/tests.py::OrganizationMembershipAccessServiceTests::test_last_active_owner_cannot_be_revoked` | 2026-09-27 | Current bootstrap assigns one `COMPANY_OWNER` role and current changes replace a role; there is no independent Tenant Owner/Tenant Admin assignment, explicit governance scope or approved backfill path | Preserve D1; revise P1.1 migration contract for independent assignments, atomic explicit bootstrap scope, final-owner protection, audit history, backfill and rollback | Accepted S07; canonical role mapping; P1.1 expand/backfill/switch/validate/rollback package and authorization | **OPEN:** same-person independent-challenge gap. No external independence rule was evidenced for D1. |
| E | E1 | **revision required** | [Q04 packet E1](P0_S14_Q04_PRODUCT_OWNER_DECISION_PACKET.md#q04-e--superuser-and-platform-admin-access); [S07 current-path finding](ADR_P0_S07_PROJECT_SITE_AUTHORIZATION.md#1-verified-current-behavior); `apps/organizations/authorization.py::{has_business_permission,require_business_permission}` grants active superusers without membership; `apps/procurement/services.py::_has_management_access`; `apps/audit/services.py::record_audit_event`; `apps/workflows/workbench.py::_authorized_membership`; evidence test: `apps/organizations/tests.py::GlobalRoleAuthorizationTests::test_system_admin_has_global_tenant_access_without_membership` | 2026-09-27 | Existing privileged paths are inconsistent: authorization helpers and procurement preserve broad superuser access, while workbench requires membership but supplies every permission code to a superuser. No Platform Admin role or scoped control/diagnostic path exists | Preserve E1; require a complete privileged-path inventory, path-by-path compatibility/cutover/rollback plan, separate Platform Admin model and negative Tenant-data access tests before behavior changes | Accepted S07; P1.1 package; D03/D04 for operator/recovery duties; security review of every direct/service/export/admin path | **OPEN:** same-person independent-challenge gap; operational/privacy external independence remains OPEN if a customer, contract or regulation requires it. |
| F | F2 Revised | **accepted with conditions** | [Q04 packet revised F2](P0_S14_Q04_PRODUCT_OWNER_DECISION_PACKET.md#q04-f--support-and-emergency-access); [S11 support contract](ADR_P0_S11_TENANT_LIFECYCLE_ENTITLEMENTS_SUPPORT.md#6-support-access-and-separation) and [gates](ADR_P0_S11_TENANT_LIFECYCLE_ENTITLEMENTS_SUPPORT.md#7-acceptance-gates-and-compatible-implementation-sequencing); [S08 Q03/D03/D05 gates](ADR_P0_S08_PRIVATE_DOCUMENT_STORAGE.md#6-decision-register-and-static-acceptance-cases); readiness register: `P0_S21_READINESS_AND_UNRESOLVED_RISK_REVIEW.md#4-open-phase-parameter-and-implementation-gates` | 2026-09-27 | No support-grant, emergency, consent, operator, expiry/revocation or compliance mechanism exists; D03 jurisdiction/operator and Q03 evidence/retention/export decisions remain OPEN | No change to F2 Revised. Support remains disabled as a future controlled path; require the normal dual-approval and separate emergency-control design to be specified without hidden impersonation | D03, Q03, D05/S11 as applicable; accepted S07; P0.2/P0.3 and a separately authorized implementation package | **OPEN:** same-person challenge gap. Any implementation of the required independent Platform approval needs a real independent human; legal/compliance independence is OPEN where applicable. |
| G | G3 Revised with Protected Operations | **revision required** | [Q04 packet final G3](P0_S14_Q04_PRODUCT_OWNER_DECISION_PACKET.md#q04-g--maker-checker-separation-and-small-tenant-fallback); [workflow/permission policy matrix](WORKFLOW_AND_PERMISSION_MATRIX.md#7-separation-of-duties-and-self-approval-baseline); current limited SoD: `apps/workflows/runtime.py::_check_sod`; current runtime tests: `apps/workflows/test_runtime.py::WorkflowRuntimeTests::test_permission_and_candidacy_are_both_required`; current configuration schema: `apps/workflows/models.py::{WorkflowStepDefinition,WorkflowTransitionDefinition}` | 2026-09-27 | No implemented Protected Operations catalogue, platform classification control, Tenant Self-Approval policy, audit model, financial/control operation matrix or cross-domain enforcement exists. Current SoD only covers configured creator/submitter/starter exclusions and may permit a configured fallback | Preserve G3; revise downstream design to create a versioned Protected Operations catalogue, policy-management boundary, business-operation classification matrix, audit evidence and explicit financial/legal control gates | Accepted S07; affected S04-S06 decisions; P1.1 authorization foundation; Q01/Q02 where financial/regulatory actions are involved; separate package authorization | **OPEN:** same-person challenge gap. Accounting/control and legal/compliance independent review remains OPEN whenever an external requirement applies. |
| H | H1 | **revision required** | [Q04 packet H1](P0_S14_Q04_PRODUCT_OWNER_DECISION_PACKET.md#q04-h--workflow-route-fallback-and-unresolved-work); [S07 workflow contract](ADR_P0_S07_PROJECT_SITE_AUTHORIZATION.md#3-enforcement-and-workflow-contract); current routing: `apps/workflows/routing.py::resolve_step_candidates`; current candidate/claim checks: `apps/workflows/runtime.py::{_active_candidate,claim_work_item,complete_work_item}`; current owner fallback test: `apps/workflows/test_runtime.py::WorkflowRuntimeTests::test_owner_fallback_operates_without_workforce`; current recovery test: `apps/workflows/test_runtime.py::WorkflowRuntimeTests::test_permission_and_candidacy_are_both_required` | 2026-09-27 | Current fallback is chosen when raw primary resolution is empty, before full target eligibility filtering; it may use `organization_owner` fallback. There is no target project/site-scope check, no defined unresolved-work administrative path and no H1-complete recheck model | Preserve H1; revise routing/workbench design to filter primary then fallback candidates by membership, permission, scope, delegation and separation; retain unresolved work and define authorized recovery without privileged auto-routing | A-C scope/delegation foundation; accepted S07; P1.1 workflow integration/cutover; unresolved-work operational procedure and negative tests | **OPEN:** same-person independent-challenge gap. No external independence rule was evidenced for H1. |

### Focused evidence conclusion

- **Q04-C:** current delegation lifecycle evidence supports interval, revocation,
  tenant and basic scope filtering, but not C1's authority-boundary or
  reassignment/recipient requirements; it is revision-required.
- **Q04-E:** the inventory above identifies the known direct privileged paths;
  it is deliberately not claimed complete until a P1.1 path-by-path inventory is
  approved and reconciled.
- **Q04-F:** F2 is policy-acceptable only because it explicitly leaves support
  disabled pending D03/Q03 and applicable legal/compliance evidence.
- **Q04-G:** the current `Protected Operations` catalogue and Self-Approval
  policy matrix are documentation policy in the Q04 packet and workflow matrix,
  not implemented runtime controls; both must become versioned design artefacts.
- **Q04-H:** current candidate checks occur on claim/completion, but the target
  primary-eligibility-first fallback rule and visible unresolved-work recovery are
  not implemented.

## 4. Supplemental evidence required before an accepted implementation outcome

For **each Q04-A through Q04-H**, supply all of the following:

1. the actual review outcome: `accepted`, `accepted with conditions`, `revision
   required`, or `not accepted`;
2. an evidence reference that can be retrieved later, with document title,
   immutable location/identifier and version (and, if available, hash or revision
   identifier);
3. the actual review date in ISO format (`YYYY-MM-DD`);
4. every unresolved objection, or the explicit value `none`;
5. every resulting revision, or the explicit value `none`; and
6. whether an external statutory, contractual, professional or customer
   independence requirement applies. If it does, provide the real independent
   reviewer and evidence; if it cannot be met, state the remaining release/gate
   restriction explicitly.

Additionally supply the following where it applies:

- Q04-A/B/D/H: the reviewed scope/parent-field or workflow classification
  inventory and its version;
- Q04-C: the reviewed delegation, revocation and authority-recheck cases;
- Q04-E: the reviewed current privileged-path inventory and compatibility/cutover
  boundary;
- Q04-F: the D03 jurisdiction/operator and Q03 consent/retention/export analysis
  that the review relied on, or an explicit statement that those dependencies
  remain open and block support enablement; and
- Q04-G: the Protected Operations catalogue and the business-operation
  Self-Approval classification matrix, including financial/control and legal
  constraints where applicable.

P0-G01 is complete as a documentation-only accountable review. The evidence above
does not accept S07 or another ADR, close P0, approve a migration, or authorize
P1. It is insufficient to change any `revision required` result to `accepted` or
to prove an implemented control.

## 5. P0-G02 disposition for P1.1 readiness

P0-G02 reconciles every G01 condition/revision into the complete P1.1 contract in
[S07 section 6](ADR_P0_S07_PROJECT_SITE_AUTHORIZATION.md#6-p0-g02-remediation-and-complete-p11-implementation-contract). A/B/F remain policy-accepted
with implementation conditions; C/D/E/G/H remain implementation requirements,
not unresolved Product Owner decisions. D03/Q03/D05/S11 and any external
independence obligation remain outside the P1.1 build boundary unless a later
package explicitly enables support/emergency, storage/export or regulated
business-operation behavior.

Accordingly, P1.1 is **READY FOR AUTHORIZATION**. This is a readiness finding,
not authorization: the Product Owner must still explicitly authorize the bounded
P1.1 implementation contract, migration/backfill/rollback work and acceptance
evidence. No ADR is accepted by this disposition.
