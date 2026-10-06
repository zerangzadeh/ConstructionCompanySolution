# P9-S06–S11 HSE / QA / CAPA Decision Packet

**Status:** **PRODUCT OWNER ACCEPTED.** On 2026-10-06 the Product Owner accepted
`P9-Q01`–`P9-Q18 = Option A`, the exact bounded runtime authorization in section
16.3, and the completed `P9-S06–S11` implementation and validation evidence in
sections 17–18.

**Prepared:** 2026-10-05

**Official envelope:** `P9-S06–S11`

## 1. Entry gate, authority, and stop boundary

The prerequisite `P9-S01–S05 = Product Owner accepted` is verified from the two
current status authorities and their implementation evidence:

- `ROADMAP.md` records `P9-S01–S05` as Product Owner accepted, including six
  focused PostgreSQL cases and rollback/reapply plus catalog validation for
  `daily_reports.0005`.
- `docs/ROADMAP_EXECUTION_PLAYBOOK.md` records the same accepted envelope and
  identifies its decision packet as authoritative for `P9-D01`–`P9-D12=A`.

This packet is the decision and implementation authority for `P9-S06–S11`. It covers HSE and
QA/QC inspections, permits, tests and test evidence, findings/nonconformities,
CAPA, verification, closure, evidence, permissions, UI, migration, and focused
acceptance. The accepted authorization covers only the bounded runtime recorded
here. APIs, notifications, queues, integrations, and production activation remain
outside this tranche; later P9 tranches through S25 are separately accepted.

Existing `SafetyIncident` and `QualityIssue` records, services, workflows,
permissions, and audit history remain authoritative for their current scope.
Planning here must not silently reinterpret, merge, backfill, or replace them.
P9.2 roadmap outcomes not named in this envelope—including risk registers,
toolbox meetings, PPE/training controls, ITP authoring as a broader planning
facility, investigations, performance metrics, and knowledge publication—remain
outside this authorization and require a later explicit envelope.

## 2. Exact session decomposition

| Session | Exact responsibility | Required output / stop condition |
| --- | --- | --- |
| `P9-S06` | Verify the entry gate and current Safety, Quality, Projects/Sites, DMS, Authorization, Audit, workflow, workforce, party, material, equipment, and field-evidence authorities. Decide the shared-kernel versus separate-engine structure and fix domain ownership/non-goals. | Ownership and engine decision are ready; existing `SafetyIncident`/`QualityIssue` compatibility is explicit. Stop before schema or runtime work. |
| `P9-S07` | Define profile-owned, versioned inspection templates/checklists; scheduling; inspector qualification reference; execution, submission, review, outcomes, findings, immutable snapshots, correction/replacement, and reinspection. | Inspection lifecycle, version pinning, evidence, terminology, and state machine are decision-ready. |
| `P9-S08` | Define source-backed permit types and rules; issuer, scope, conditions, validity, evidence, review/issue, suspension/reinstatement, revocation, expiry, renewal/replacement, and optional project/site/activity/equipment links. | Permit lifecycle fails closed when an applicable rule or evidence is missing; no statutory category, period, or threshold is invented. |
| `P9-S09` | Define QA/QC test requests; method/specification versions; samples/specimens; performer/laboratory identity; execution/results; acceptance criteria; evidence; review; invalidation/supersession; and retest lineage. | Test/result authority and immutable reviewed-result lineage are decision-ready; no technical standard or limit is invented. |
| `P9-S10` | Define HSE/QA finding classification, explicit QA NCR promotion, assignment/disposition/correction, CAPA trigger and distinct corrective/preventive actions, implementation, verification, effectiveness, reopen, and closure. | Finding/NCR/CAPA boundaries, person-level separation, state machines, audit, concurrency, and downstream no-effects are decision-ready. |
| `P9-S11` | Consolidate Product Owner decisions, permission catalogue, Persian-first RTL workbenches, expand-only migration, PostgreSQL acceptance, residual risks, and exact bounded future runtime authorization; reconcile roadmap/playbook. | The decision register was ready for explicit disposition before runtime authorization; later P9 tranches through S25 were separately accepted. |

## 3. Bounded architecture and authoritative ownership

### 3.1 Recommended bounded structure

Use one shared inspection/CAPA infrastructure with mandatory typed profiles,
while preserving separate HSE and QA/QC business authorities and terminology.
The shared kernel may own only common mechanics: version-pinned template
snapshots, execution identity, checklist responses, evidence bindings, lifecycle
history, assignments, idempotency, and transition enforcement. Each profile owns
its catalogue, required qualifications, severity/classification, outcomes,
finding semantics, permit/test applicability, CAPA policy, and visible vocabulary.

There is no generic tenant-authored engine, executable expression language, or
untyped cross-domain record. Platform-controlled catalogues and source-backed,
versioned Tenant configurations remain bounded by registered validation. Shared
workflow may coordinate work after implementation authorization; HSE/Quality
services remain authoritative for domain transitions.

### 3.2 Ownership map

| Information / behavior | Authoritative owner | Boundary |
| --- | --- | --- |
| Shared inspection execution mechanics and immutable transition/snapshot lineage | Shared HSE/Quality inspection kernel | Requires a mandatory `HSE` or `QA_QC` profile; never owns profile meaning. |
| HSE template/checklist content, inspection policy, HSE outcome/finding taxonomy | HSE / Safety | HSE terminology and permissions remain distinct from QA/QC. |
| QA/QC template/checklist content, inspection policy, acceptance profile, QA finding/NCR taxonomy | Quality | A checklist may cite a test/specification but does not become the test or specification authority. |
| Template publication/version | Owning HSE or Quality profile through common version mechanics | Published versions are immutable. Executions pin one exact version and a canonical snapshot; later edits create a new version. |
| Inspection execution and responses | Owning profile, using shared mechanics | Owns schedule/execution/outcome only; it cannot mutate the inspected Project, Site, activity, Equipment, material, contract, stock, or cost fact. |
| HSE finding | HSE / Safety | May originate from an HSE inspection or authorized manual source; it is not a QA NCR. |
| QA/QC finding | Quality | Remains a finding until an authorized classification explicitly promotes it to a formal NCR where applicable. |
| Formal nonconformity/NCR | Quality | Has its own number, disposition, lifecycle, and lineage; it may cite one or more QA findings/test results. |
| Permit record and HSE permit lifecycle | HSE / Safety | Permit type/rule is source-backed configuration. External/statutory issuer identity may be recorded; the ERP does not claim legal issuance authority it does not possess. |
| Test request, specimen/sample identity, execution, result, review, invalidation, retest lineage | Quality | Laboratory/performer supplies evidence; Quality owns the governed ERP record. A result never overwrites its request, method, sample, or prior result. |
| Test method/specification reference and acceptance criteria | The existing authoritative external/internal specification source, pinned by Quality | Store an exact source/version/snapshot. Do not invent or silently update limits. DMS owns associated document versions. |
| Corrective and preventive action | Source profile (HSE or Quality) using shared CAPA mechanics | Action type and source are mandatory. An action does not replace the source finding/NCR/incident/issue. |
| Verification, effectiveness review, closure, and reopen history | Source profile domain | Domain service re-checks authority and separation. History is append-only and reasoned. |
| Document/media bytes, immutable versions, hashes, previews/derivatives, confidentiality, retention, legal hold, export, and recovery | **DMS alone** | Domain-owned typed links pin exact DMS versions; no attachment/blob store is added. |
| Project/site/phase/activity identity and scope | Projects/Sites | HSE/Quality stores validated references and necessary historical snapshots only. |
| Workforce qualification/training evidence | Workforce | HSE/Quality may require and pin/reference an effective qualification fact; it does not create a parallel employee/training master. |
| Business-party/laboratory identity | BusinessParty / existing party authority | A performer snapshot may be retained for history. P9-S12+ partner evaluation is not implemented here. |
| Material/equipment identity | Materials and Equipment | Reference-only. No stock, custody, maintenance, valuation, or equipment-state mutation. |
| Contract, Procurement, Inventory, Equipment, Project Cost, Accounting, Payroll, Treasury, Fixed Assets facts | Their existing respective authorities | HSE/Quality may cite identities or prepare an explicit proposal; it cannot create, approve, post, reverse, or mutate their facts. |

## 4. Inspection architecture

### 4.1 Templates and versions

A template has Tenant, profile, platform-controlled template kind, owning scope,
title/code, applicability, required inspector-qualification references, evidence
policy, outcome rule, and lifecycle. A version contains ordered sections/items,
response types, required flags, controlled option sets, evidence requirements,
finding triggers, and any source-backed specification references.

Recommended template lifecycle:

`draft -> under_review -> published -> retired`

- only drafts are editable;
- review/publish require explicit permissions and a nonempty, deterministic
  validation result;
- publication allocates an immutable version and content hash;
- retirement blocks new scheduling but never changes existing executions; and
- correction after publication creates a new linked version with a reason.

Tenant configuration may assemble platform-registered item/condition types but
may not execute Python, SQL, templates, callbacks, or arbitrary expressions.

### 4.2 Scheduling, execution, outcomes, and history

An inspection may be created ad hoc when policy permits or from a schedule. A
schedule records recurrence/configuration only; notifications/jobs remain outside
this envelope. Creation pins the exact published template version and scope.
The designated inspector must have active membership, permission, object scope,
and any configured effective qualification evidence at execution/submission.
Positions route candidates but never grant permission.

Inspection lifecycle:

`draft -> scheduled -> in_progress -> submitted -> under_review -> passed | conditional | failed`

An authorized ad hoc inspection may transition directly from `draft` to
`in_progress`; scheduling is not fabricated when it did not occur.

Additional transitions:

- `draft -> cancelled` or `scheduled -> cancelled` before execution, with reason;
- `in_progress -> cancelled` only when no submitted evidence exists, with reason;
- `submitted -> under_review` is idempotent and does not unlock responses;
- a reviewer may return by creating a linked correction execution, not by editing
  the submitted snapshot;
- `conditional` requires explicit unresolved conditions/findings and their owner;
- `failed` records failed items/findings but creates no downstream stop action;
- any reinspection is a new execution linked to the prior inspection and relevant
  finding/NCR; and
- an erroneous finalized inspection may be marked `superseded` only by a linked,
  reviewed replacement. The original remains immutable and visible.

The submitted snapshot pins template version/hash, responses, not-applicable
reasons, actor/membership, authoritative server times, client-claimed capture
time where used, scope snapshots, outcome inputs, and exact DMS evidence versions.
Outcome calculation must be deterministic from the pinned version; any authorized
manual override is explicit, reasoned, permissioned, and audited.

## 5. Permit lifecycle

A permit records a source-backed permit type/rule version, issuer/issuing
authority, holder/responsible party, Tenant and project/site scope, optional
activity/equipment references, proposed and approved validity period, conditions,
prerequisites, evidence, and replacement lineage. Applicability, duration,
thresholds, required evidence, and suspension/revocation rules are never invented.
If an applicable source/rule, required qualification, or evidence is absent or
expired, issue/reinstatement/renewal fails closed.

Permit state machine:

`draft -> submitted -> under_review -> issued`

From `issued`:

- validity is computed from the approved period plus current suspension,
  revocation, and replacement state; `expired` is an explicit recorded projection
  or transition and never extends validity;
- `issued -> suspended -> reinstated` requires reason, actor, time, and rechecked
  prerequisites;
- `issued/suspended -> revoked` is terminal for that permit;
- renewal creates a new reviewed permit linked as successor; it never edits the
  original period; and
- replacement/supersession preserves both records and exact evidence.

`draft/submitted/under_review -> cancelled` is allowed with reason. `expired`,
`revoked`, `cancelled`, and `superseded` are terminal for that identity. The ERP
records evidence and control status; it does not assert statutory validity beyond
the cited source and issuer authority. Permit state never automatically starts or
stops work, changes Equipment status, or approves a contract.

## 6. Tests and QA evidence

A test request owns its Tenant/project/site context, requesting actor, tested
subject reference, exact method/specification source and version, required
acceptance-criteria snapshot, sample/specimen identities and custody metadata
where applicable, requested performer/laboratory, due time, and evidence policy.
Samples/specimens require stable, non-reused identifiers within their configured
scope; custody events are append-only. A laboratory/performer identity and any
qualification/accreditation claim are source-backed snapshots, not silently
trusted current facts.

Test lifecycle:

`draft -> requested -> scheduled -> in_execution -> result_entered -> under_review -> accepted | rejected`

- `draft -> cancelled`, `requested -> cancelled`, or `scheduled -> cancelled`
  requires reason;
- result entry pins method/specification/criteria, units, raw values, conditions,
  performer, times, specimen, calculation/version evidence, and DMS evidence;
- the system evaluates only configured, versioned criteria it can represent
  deterministically; otherwise an authorized reviewer records a sourced decision;
- submitted results are immutable;
- a materially erroneous result becomes `invalidated` with reason and authority;
- a corrected result is a new linked result and the former becomes `superseded`
  only after review; and
- a retest is a new request/execution linked to the original result and reason.

Acceptance or rejection is a QA evidence decision only. It does not approve a
material master, release Inventory, accept contract work, certify a Claim, post a
cost, or change Equipment without an independently authorized consumer handoff.

## 7. Findings, nonconformity, and disposition

An inspection finding is a scoped observation requiring triage. It records
profile, source inspection/test/manual authority, classification/severity source,
description, responsible party/assignee, due date where required, evidence, and
history. Not every finding is an NCR.

Finding lifecycle:

`recorded -> triaged -> assigned -> correction_in_progress -> pending_verification -> verified -> closed`

- `recorded -> dismissed` requires an authorized reason and retains evidence;
- triage selects classification, severity, disposition, and whether formal NCR or
  CAPA is required under a pinned rule;
- a closed/verified finding may be `reopened -> assigned` when verification fails,
  recurrence is detected, or material evidence changes; reason is mandatory; and
- source inspection/test history is never edited by finding transitions.

For QA/QC only, authorized classification may create a distinct formal NCR linked
to the source finding(s) or failed test. NCR lifecycle:

`draft -> issued -> disposition_pending -> action_in_progress -> pending_verification -> verified -> closed`

Disposition is an explicit controlled value under the pinned QA policy (for
example correction/rework or another configured disposition); this packet does
not invent contractual acceptance, concession authority, or technical options.
An erroneous NCR may be `voided` only with reason and, where applicable, a linked
replacement. `closed -> reopened -> action_in_progress` preserves the prior
closure and verification. HSE findings remain HSE findings; incidents remain
`SafetyIncident` unless a separately authorized relationship is recorded.

## 8. CAPA, verification, effectiveness, and closure

Correction contains the immediate fix or containment of the detected condition.
Corrective action addresses an evidenced cause to prevent recurrence. Preventive
action addresses an evidenced risk before occurrence. Verification establishes
that the declared action was implemented and the condition meets the pinned
criteria. Effectiveness review evaluates, after an appropriate source-backed
period or evidence threshold, whether the action achieved its intended systemic
effect. These are distinct records/evidence and must not be collapsed into one
free-text field.

A CAPA has mandatory source/profile, type (`corrective` or `preventive`), problem
or risk statement, cause/rationale evidence, responsible membership/employee or
BusinessParty reference, target date, implementation plan, required evidence,
verification criteria, effectiveness criteria/timing, and immutable history.

CAPA lifecycle:

`proposed -> approved -> assigned -> in_progress -> pending_verification -> verified -> effectiveness_pending -> effective -> closed`

- `proposed -> rejected` and pre-work `approved/assigned -> cancelled` require
  authority and reason;
- failed verification returns a new history entry to `in_progress`;
- `effectiveness_pending -> ineffective -> reopened -> in_progress` preserves the
  complete prior action, verification, and effectiveness evidence;
- closure is allowed only after required verification and effectiveness review,
  unless a pinned policy explicitly and visibly marks effectiveness review not
  applicable with authority and reason; and
- `closed -> reopened -> in_progress` requires `reopen` permission, reason, and
  a new target/assignment review. No prior history is overwritten.

Recommended protected-operation separation is narrow: the person who records
implementation completion cannot verify that implementation. The verifier may
close after successful verification/effectiveness review unless a pinned
severity/profile policy requires a distinct closer. The reporter/creator may be
the assignee where authorized. No universal creator/resolver/closer separation is
imposed. All checks use person identity, not merely roles or positions.

## 9. Evidence and DMS contract

Each inspection, permit, test request/result, finding, NCR, CAPA action,
verification, effectiveness review, closure, reopen, invalidation, and
replacement may have a small domain-owned typed evidence-link table. Every link
must include Tenant, domain record, evidence purpose/type, exact DMS
`DocumentVersion`, its recorded hash/integrity metadata, linking actor/time, and
source/provenance where applicable.

DMS remains the sole authority for bytes, immutable versions, derived previews,
classification, retention, legal hold, secure download/export, and recovery. A
later DMS version is not silently substituted. Sensitive-case access requires
both domain-object permission/scope and a separate sensitive-evidence permission;
a document permission alone does not broaden HSE/QA access. Evidence removal is a
reasoned unlink/withdrawal history where policy allows, never deletion of the DMS
version or erasure of finalized lineage.

## 10. Permissions and object scope

Future implementation must introduce explicit `BusinessPermissionCode` entries,
registry resources, data-migration catalogue/default-role grants, service/view
enforcement, and tenant/project/site tests. Candidate capability codes are:

| Capability | Required permission boundary |
| --- | --- |
| Template management | view; create draft; review; publish/retire |
| Inspection | view; create/schedule; execute; submit; review/outcome; supersede/reinspect |
| Finding | create; classify/triage; assign/manage |
| Permit | view; prepare/submit; review/issue; suspend/reinstate; revoke/replace |
| Test | view; request; execute/result entry; review/accept-reject; invalidate/retest |
| NCR | view; create/issue; classify/disposition; manage |
| CAPA | view; assign/approve; execute/record implementation |
| Verification/effectiveness | verify; record effectiveness decision |
| Closure/reopen | close; reopen |
| Evidence | link ordinary evidence; access sensitive evidence |
| Assurance | export; audit/reconciliation view/run |

Every operation re-resolves active membership, active Tenant, permission,
project/site scope, record Tenant, record state, assignment/candidacy where
required, and person-level separation inside the transaction. Tenant-wide roles
do not bypass accepted project/site object scope. Position and workforce
qualification route/filter work but never grant authorization. Consequential
actions deny by default; UI visibility is not authority.

## 11. Workflow, audit, concurrency, and idempotency

Domain services own all state machines. Shared workflow may call registered HSE
or Quality commands and route work; it cannot generically mutate state. Every
transition records actor/user and membership, authoritative server time,
previous/new state, reason, source/request identity, assignment/qualification
evidence where applicable, pinned policy/template/specification versions,
evidence links, and correlation identity. Publish, submit, outcome, issue,
suspend/revoke, result review/invalidation, NCR disposition, CAPA approval,
verification, effectiveness, close, reopen, replace, export, and sensitive access
are auditable events.

Mutation services use `transaction.atomic()`, lock and re-read the aggregate plus
relevant current version/assignment using `select_for_update()`, re-check
permission/scope/separation inside the transaction, and reject stale expected
state/version. Database constraints enforce Tenant-scoped identifiers, one active
published template version where applicable, valid lineage (no self/cycles), and
single accepted transition/request keys. Client operation keys are opaque,
Tenant/actor/action scoped, payload-hash bound, and return the original result for
an exact retry while rejecting key reuse with a different payload. Schedule,
inspection, result, NCR, and CAPA business identities prevent duplicate creation.

Finalized/submitted snapshots and transition histories are append-only at the
application layer. Corrections, invalidations, supersession, reinspection,
retests, and reopen operations create linked evidence; they never rewrite history.

| Aggregate | Protected transition authority | Terminal/recovery rule | Retry/stale-state rule |
| --- | --- | --- | --- |
| Template | profile template reviewer/publisher | `retired` blocks new use; correction is a new version | publish key plus expected draft version; one exact replay |
| Inspection | inspector executes/submits; inspection reviewer decides outcome | `cancelled`, `passed`, `conditional`, `failed`, and `superseded` are final for that execution; correction/reinspection is linked new execution | operation key plus expected state/template version |
| Permit | preparer submits; permit reviewer/issuer issues; separately permissioned actor suspends, reinstates, revokes, or replaces | `cancelled`, `expired`, `revoked`, and `superseded` are final; renewal/replacement is new identity | operation key plus expected state/rule version and validity inputs |
| Test | requester requests; authorized performer enters; test reviewer accepts/rejects/invalidates | reviewed result is immutable; `cancelled`/`invalidated` are final; correction/retest is linked new record | request/result identity plus expected state/method/criteria version |
| Finding/NCR | classifier triages/promotes; assignee corrects; verifier verifies; closer closes | dismissal/void are reasoned; closed records reopen only through a new history cycle | source/type business key plus expected state/classification version |
| CAPA | approver approves; assignee implements; independent verifier verifies; effectiveness reviewer decides; closer closes | rejected/cancelled are terminal; ineffective/closed may reopen with retained history | action/transition key plus expected state, action version, and separation re-check |

## 12. Downstream proposal-only boundary

Inspection, permit, test, finding, NCR, and CAPA records are evidence/control
facts only. They cannot automatically start/stop project execution, update a
schedule, mutate Project Cost, Inventory, Equipment, Contracts, Procurement,
Claims, Accounting, AP/AR, Treasury, Payroll, or Fixed Assets, or create a
knowledge publication.

Where a downstream response is needed, the source domain may prepare an explicit,
immutable, reviewed proposal/handoff containing source identity/version, target
domain/type, Tenant/project/site scope, facts and evidence, preparer/reviewer,
idempotency key, and acknowledgement status. The receiving domain independently
authorizes and creates its own draft/fact through its service. Rejection or
acknowledgement never changes the HSE/QA source history. No generic consumer or
automatic finalization is authorized.

## 13. Expand-only migration and retention

Migration is expand-only and non-fabricating:

1. add new nullable/independent structures, constraints, catalogues, and typed DMS
   link support only after decisions and runtime authorization;
2. preserve every existing `SafetyIncident`, `QualityIssue`, permission,
   transition, actor, and audit record unchanged;
3. do not infer templates, inspections, findings, permit state, test requests or
   results, NCRs, CAPA type/action, verification, effectiveness, closure, or
   person-level separation from legacy text/status fields;
4. allow explicit future links to existing records only when authoritative source
   identity and lineage are proven and recorded; absence remains absence;
5. link an existing historical DMS document only when exact document version,
   Tenant, source, and domain lineage are authoritative; and
6. switch consumers only after backfill/reconciliation reports show no fabricated
   facts or cross-Tenant/project links. Contract/removal remains separately
   authorized.

Recommended retention is no ordinary hard deletion after submission/issue/result
entry/NCR issuance/CAPA approval. Finalized domain history follows Tenant/DMS
retention and legal hold, with evidence-class schedules configurable only from an
approved source. Draft disposal may follow a separately approved schedule and
audit. Legal/statutory retention periods are unresolved and must not be invented.

## 14. Persian-first RTL workbenches and focused acceptance

### 14.1 UI contract

Provide separate, clearly named Persian-first RTL entry points for HSE inspections
and findings and for QA/QC inspections, tests, NCRs, and CAPA. Shared mechanics do
not justify mixed terminology. Required views include inspection plan/execution,
findings triage, permits/validity exceptions, test requests/results/specimen
lineage, NCR disposition, CAPA assignment/execution, verification/effectiveness,
closure/reopen, exceptions/overdue, and audit/history.

Field execution is responsive online-first Django UI: large touch targets,
one-hand ordering, clear save/submission state, camera/file handoff to DMS,
attachment progress/retry, retained accepted uploads after validation errors,
Jalali dates and Persian numerals, explicit mixed-direction isolation, accessible
labels/focus/errors, and compact desktop tables with mobile containment/row
summaries. General offline synchronization, native apps, background upload,
notifications, and device management remain unauthorized. Sensitive evidence and
actions are omitted from navigation and denied server-side when unauthorized.

### 14.2 Focused PostgreSQL acceptance requirements

Future implementation is accepted only with targeted PostgreSQL evidence for:

1. cross-Tenant read/write/link denial and active-Tenant lifecycle enforcement;
2. project/site/phase/activity consistency and object-scope denial;
3. every permission family, assignment/candidacy, qualification reference, and
   protected verifier/implementer separation;
4. template publication immutability, exact execution version/hash pinning, and no
   historical change after a new version;
5. inspection schedule/ad-hoc execution, immutable submission, deterministic
   outcome, correction/replacement, reinspection, and duplicate retry;
6. source-backed permit issue, computed validity/expiry, suspend/reinstate,
   revoke, renewal/replacement, and fail-closed missing/expired prerequisites;
7. request-method-specification-criteria-specimen-result lineage, review,
   invalidation/supersession, retest, units/precision, and no invented limits;
8. finding triage/dismissal/assignment/correction, explicit QA NCR promotion,
   disposition, verification, closure, and reopen history;
9. distinct correction/corrective/preventive records, CAPA assignment/execution,
   failed/successful verification, effectiveness failure/reopen, and closure;
10. exact DMS-version/hash evidence, sensitive-access denial, retention/hold, and
    missing/withdrawn evidence behavior;
11. locking races, stale-state rejection, unique business identities, exact retry
    replay, mismatched-payload key rejection, and transition idempotency;
12. audit completeness, immutable submitted/finalized history, export scope, and
    reconciliation exceptions;
13. explicit proof that no tested transition mutates Projects/Sites execution,
    Project Cost, Inventory, Equipment, Contracts/Claims, Procurement, Accounting,
    AP/AR, Treasury, Payroll, Fixed Assets, or production state; and
14. Persian-first RTL navigation, terminology separation, permissions, Jalali
    dates, mobile/desktop responsive use, accessibility, validation preservation,
    and mixed-direction rendering.

The smallest relevant Django checks, targeted tests, Ruff scope, migration
forward/rollback/reapply rehearsal, and PostgreSQL catalog constraints/indexes/FKs
must be recorded. Full-suite or production activation is not implied.

## 15. Product Owner decision register

Every recommendation below is **pending**. Selecting an option must record the ID,
choice, variations, date, and approver. Avoidable implementation choices may not
be deferred silently.

| ID / decision | A — recommended | Other realistic option(s) | Consequence | Sessions |
| --- | --- | --- | --- | --- |
| `P9-Q01` HSE/QA engine | One shared mechanics kernel with mandatory typed HSE and QA/QC profiles; each profile owns policy, terminology, classification, and authority | B: wholly separate engines; C: one untyped combined engine | A avoids duplicated lifecycle/evidence code without merging business meaning. B duplicates controls; C weakens authority and language. | S06–S11 |
| `P9-Q02` template/version ownership | Owning HSE or Quality profile publishes immutable versions through shared version mechanics; execution pins version/hash/snapshot | B: central DMS-owned templates; C: editable live checklist | A preserves domain authority and history. DMS owns documents, not checklist semantics; C is nonconforming. | S06–S07 |
| `P9-Q03` inspection initiation and field client | Authorized ad hoc plus optional schedules; responsive online-first web, server drafts/idempotent retry, no durable offline | B: schedule-only; C: separately approved encrypted offline/native client | A serves field work within current platform/security boundaries. C needs a separate device/sync contract. | S07, S11 |
| `P9-Q04` outcome/correction | Deterministic passed/conditional/failed from pinned rules, with permissioned reasoned override; submitted records immutable; correction/reinspection is linked new execution | B: reviewer-only free judgment; C: edit submitted execution | A is explainable and preserves history. C is nonconforming. | S07 |
| `P9-Q05` finding versus NCR | Every observation begins as typed HSE/QA finding; only authorized QA classification creates a distinct NCR | B: every failed item becomes NCR; C: findings and NCR are one record | A keeps proportional control and formal NCR lineage. B creates noise; C obscures formal issuance. | S07, S09–S10 |
| `P9-Q06` permit lifecycle | Source-backed configurable type/rule, reviewed issue, computed validity, suspend/reinstate, revoke, and renewal by linked replacement; fail closed | B: evidence-only register without internal issue decision; C: fixed statutory categories/periods | A provides control without inventing law. B may be selected where ERP cannot issue; C is prohibited absent sources. | S08 |
| `P9-Q07` test/result authority | Quality owns governed request/result/review; performer/lab is evidenced party; exact source/version criteria and specimen lineage are pinned | B: laboratory integration is authority; C: inspection owns raw result | A works without integration and preserves QA accountability. B requires a later integration contract. | S09 |
| `P9-Q08` invalid result/retest | Reviewed result is immutable; invalidation is reasoned; correction/supersession and retest use new linked records | B: edit reviewed result; C: delete and replace | A preserves scientific/audit lineage. B/C are nonconforming. | S09 |
| `P9-Q09` CAPA structure | Shared mechanics with profile-owned CAPA; separate action items and explicit type, source, owner, target, evidence, verification and effectiveness | B: one free-text action on finding/NCR; C: standalone CAPA domain detached from source | A supports multiple governed actions without losing HSE/QA ownership. | S10–S11 |
| `P9-Q10` correction boundary | Correction/containment is distinct from corrective action; preventive action is distinct from both and requires evidenced risk rationale | B: combine correction and corrective action; C: omit preventive action | A prevents immediate fixes being misrepresented as systemic action. | S10 |
| `P9-Q11` verification authority | Separate permission; assigned active member with scope and configured competence; implementer cannot verify own implementation | B: any manager may verify; C: implementer may self-verify | A protects the consequential evidence decision with narrow person-level separation. | S10–S11 |
| `P9-Q12` closure authority | Separate close permission; verifier may close after all gates; pinned critical-profile policy may require a distinct closer | B: always different verifier and closer; C: implementer may close | A avoids universal bureaucracy while protecting configured high-risk closure. | S10–S11 |
| `P9-Q13` creator/resolver/verifier/closer SoD | No blanket creator/assignee separation; mandatory implementer-versus-verifier separation; extra distinct closer only by pinned risk policy | B: four different people always; C: no person-level separation | A applies SoD only to the protected verification operation and permits small-contractor operation. | S10–S11 |
| `P9-Q14` reopen | Authorized reasoned finding/NCR/CAPA reopen from verified/closed/ineffective outcomes to a new in-progress cycle; preserve prior verification/closure, reassess owner/date/evidence. Final inspection/test correction uses reinspection/retest instead | B: terminal closure; C: mutate prior closure | A supports recurrence/error without erasing history while preserving execution/result identity. | S07–S11 |
| `P9-Q15` downstream effects | Evidence/control facts only; reviewed immutable proposal/handoff; consumer independently authorizes and creates its own record | B: named automatic stop/block for a separately approved protected case; C: generic automatic effects | A preserves all domain authorities and current no-effect gates. B requires its own explicit consumer and failure contract. | S06–S11 |
| `P9-Q16` sensitive evidence | Domain object permission plus separate sensitive-evidence permission, DMS classification, purpose-limited audit, and scoped export | B: ordinary DMS view permission; C: profile-wide unrestricted access | A prevents document access from bypassing HSE/QA case sensitivity. | S06–S11 |
| `P9-Q17` retention | No ordinary hard delete after submission/issue/result/NCR/CAPA approval; Tenant/DMS policy and legal hold apply; class-specific periods remain source-backed | B: fixed platform period; C: Tenant user may delete finalized history | A preserves evidence without inventing legal periods. | S06–S11 |
| `P9-Q18` mobile/field requirements | Responsive online-first Persian RTL web, large-touch execution, DMS upload progress/retry, server drafts, no durable offline/native runtime | B: desktop-first only; C: separately approved native/offline client | A meets bounded field use with current architecture. C needs security, device-loss, sync/conflict, purge, and operational approval. | S07, S11 |

## 16. Preserved gates, acceptance gate, and exact authorization wording

### 16.1 Preserved gates

Following the bounded authorization, this packet preserves all of the following:

- only the section 16.3 `P9-S06–S11` runtime is authorized; every `P9-S12+`
  session remains unauthorized;
- notifications, reminders/escalation delivery, queues, scheduled/background jobs,
  APIs, external laboratory/regulator integrations, native/offline clients,
  knowledge publication, metrics/BI activation, and production activation remain
  unauthorized;
- Project Cost actuals, Accounting/GL, AP/AR, Treasury/cash, Payroll, Inventory,
  Equipment, Fixed Assets, Contracts/Claims approval, Procurement, and project
  execution receive no automatic mutation; and
- unresolved statutory categories, validity periods, technical standards,
  acceptance limits, qualifications, and retention periods remain source-backed
  configuration and fail closed.

### 16.2 Decision acceptance gate — fulfilled

The Product Owner recorded `P9-Q01`–`P9-Q18 = Option A`, reconciled the affected
active documents, accepted the permission catalogue/default grants, and issued the
bounded runtime authorization below. Completion acceptance is recorded in section
18; it does not broaden the authorization boundary.

### 16.3 Exact bounded runtime authorization wording

> Product Owner authorizes implementation of `P9-S06–S11` only, exactly within
> the accepted `P9-Q01`–`P9-Q18` decisions and the boundaries of the
> `P9-S06–S11 HSE / QA / CAPA Decision Packet`. Authorization covers only the
> approved tenant/project/site-scoped HSE and QA/QC inspection, permit, test,
> finding/NCR, CAPA, verification/closure, exact DMS-version evidence,
> permissions, Persian-first RTL adapters, expand-only migrations, audit,
> concurrency/idempotency controls, and focused PostgreSQL acceptance evidence.
> It does not authorize `P9-S12+`, inferred legacy history, notifications, queues,
> scheduled/background jobs, APIs, external integrations, native/offline clients,
> knowledge publication, production activation, or automatic mutation of
> Projects/Sites execution, Project Cost, Inventory, Equipment, Contracts/Claims,
> Procurement, Accounting/GL, AP/AR, Treasury, Payroll, or Fixed Assets. DMS
> remains the sole byte/version authority, receiving domains remain sole fact
> authorities, and unresolved legal/technical rules fail closed.

The Product Owner accepted that text without variation on 2026-10-06.

## 17. Accepted decisions and implementation evidence (2026-10-06)

- `P9-Q01`–`P9-Q18 = Option A` are accepted exactly as recorded in section 15.
- `apps.compliance` implements the tenant/project/site-scoped shared mechanics
  kernel with mandatory `HSE` and `QA/QC` profiles. Separate profile ownership,
  terminology and consequential permissions are preserved.
- Immutable template versions and inspection snapshots, permit validity and
  replacement, QA test/result/retest lineage, findings versus explicit QA NCR,
  and correction/corrective/preventive CAPA with verification, effectiveness,
  close and reopen history are implemented.
- Domain services enforce permission and object scope, row locking, stale-state
  rejection, operation-key replay checks, implementer/verifier separation and
  configurable distinct critical closer policy. Lifecycle evidence is appended to
  the existing audit system.
- Domain-owned evidence links register with DMS, pin exact `Document` and
  `DocumentVersion` identities plus hash, and require the separate sensitive
  evidence permission. DMS remains the only byte/version authority.
- Persian-first RTL workbench, mutations, evidence/history, scoped CSV export and
  reconciliation exception view are reachable from normal navigation.
- One expand-only compliance schema migration and one permission-catalogue data
  migration add no inferred legacy HSE/QA history. Focused clean-schema PostgreSQL
  acceptance passed: `10 passed`, including tenant/profile boundaries, immutable
  lineage, permit/test/finding/NCR/CAPA behavior, DMS authorization, no-effect
  proposals, a real transition race, and bounded migration rollback/reapply.
- Django system check, migration-drift check, targeted Ruff, template compilation
  and diff hygiene passed at closeout.

## 18. Product Owner acceptance (2026-10-06)

The Product Owner accepts `P9-S06–S11` as implemented. The accepted scope is the
shared typed HSE/QA mechanics and separate business authority; versioned and
immutable inspections; fail-closed source-backed permits; QA test/result/retest
lineage; findings versus formal NCR; CAPA through verification, effectiveness,
close and reopen; transactional stale-state/idempotency controls; audit; exact DMS
evidence pins and sensitive access; RTL/Jalali workbenches; scoped export and
reconciliation; and proposal-only downstream handoffs.

The acceptance validation record is: clean-schema PostgreSQL `10 passed in
627.46s`; real concurrent stale-state race, sensitive DMS denial, CAPA separation,
UI/export/reconciliation coverage, and bounded compliance migration rollback/
reapply passed; Django system check, migration-drift check, targeted Ruff, template
compilation, and `git diff --check` passed. The broad application suite was
intentionally not run and is not required for this bounded tranche.

Accepted migrations are `compliance.0001_initial` and
`organizations.0101_p9_s06_s11_compliance_permissions`; they are expand-only and
non-fabricating. No existing SafetyIncident, QualityIssue, audit, workflow, permit,
test, NCR, CAPA, verification, or closure history is inferred or rewritten.

`P9-S12+`, notifications, queues/schedulers, external integrations, native/offline
expansion, knowledge publication, production cutover/activation, and every
automatic downstream effect remain unauthorized. Missing legal or technical rules
remain fail-closed.
