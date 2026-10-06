# P9-S25 Final Privacy, Evidence and Workflow Review Decision Packet

**Status:** **PRODUCT OWNER ACCEPTED.**  
**Official envelope:** `P9-S25` only.  
**Verified prerequisite:** `P9-S01–S24 = Product Owner accepted`; cumulative result: `P9-S01–S25 = Product Owner accepted`.  
**Prepared:** 2026-10-06.
**Runtime authorized:** 2026-10-06; `P9-F01`–`P9-F18 = Option A` and section 19 accepted exactly.  
**Assurance completed:** 2026-10-06.

This is the authoritative decision and implementation/assurance record for the
final P9 assurance session. The accepted authorization covered S25 only; it did
not authorize jobs, queues, integrations, production activation, or `P9-S26`.

## 1. Verified scope and authority

The execution playbook defines exactly one S25 session: **field privacy, evidence
integrity, notification/workflow and Knowledge final review**. Before the recorded
authorization, the Roadmap kept `P9-S25+` unauthorized after accepting S01–S24.
The accepted P9 packets establish the binding baseline:

- `P9-D01`–`P9-D12=A`: Tenant/project-scoped Field observations, minimized and
  untrusted location, DMS-only bytes, exact version/hash evidence, immutable
  submission/review/correction, and proposal-only downstream behavior;
- `P9-Q01`–`P9-Q18=A`: typed HSE/QA controls, exact evidence, immutable reviewed
  results, narrow risk-based SoD, CAPA verification/effectiveness history, and no
  automatic downstream effects;
- `P9-P01`–`P9-P18=A`: Tenant-local partner facts, exact DMS evidence, explainable
  evaluation, immutable correction/appeal, narrow reviewer separation, and
  proposal-only handoff;
- `P9-N01`–`P9-N18=A`: source-linked in-app notification/support evidence,
  consented diagnostics, DMS pins, time-bounded access proposals, existing
  WorkItem authority, no provider/scheduler, and no downstream mutation; and
- `P9-K01`–`P9-K24=A`: reviewed derivative Knowledge, immutable publication,
  exact provenance, deterministic recurrence, typed reuse evidence, restricted
  Platform promotion, and no AI or downstream effect.

S25 is therefore primarily cross-domain assurance and reconciliation. It may
identify narrowly bounded hardening of existing controls, but it cannot create a
new privacy engine, evidence store, workflow authority, notification channel,
document store, policy authority, or business-domain effect.

## 2. Assurance classification

| Review area | Primary S25 classification | Boundary |
| --- | --- | --- |
| Accepted ownership, lifecycle and no-effect rules | Assurance-only | Re-prove; do not redesign. |
| Cross-domain terminology/status and invariant matrix | Documentation reconciliation | One explanation; domain records remain distinct. |
| Cross-domain PostgreSQL regression | Test/assurance only | Target shared boundaries, not every prior module. |
| Raw precise location and sensitive field metadata access | Candidate configuration/permission hardening | Only if inspection proves ordinary view currently exposes more than minimum necessary. |
| Sensitive-state warning/masking on existing screens and exports | Candidate bounded runtime hardening | Only proven gaps; no new UI subsystem. |
| Notification payload minimization/source revalidation | Candidate bounded runtime hardening | In-app only; source facts stay authoritative. |
| Missing/stale evidence presentation | Candidate bounded runtime hardening | Status/warning projection only; never rewrite history. |
| New providers, schedulers, broad export platform, AI or production controls | Deferred to P10 or later | Not authorized by S25. |

## 3. Final field-privacy contract

### 3.1 Data classification and minimum necessary handling

| Field-originated data | Required/optional | Treatment |
| --- | --- | --- |
| Server-resolved Tenant, authorized project and observation identity | Required | Canonical scope; never accepted from client claims as authority. |
| Site/phase/activity | Optional unless the governed observation type requires it | Same-Tenant/project validation; retain exact historical identity. |
| Creator, submitting membership, reviewer and server transition times | Required for the applicable transition | Historical accountability; do not copy workforce/person profiles. |
| Title, bounded summary and structured payload version | Required | Minimum operational description; sensitive free text remains access-controlled. |
| Client `captured_at`, offset and effective date | Optional as applicable | Mark client-supplied; server receipt/transition time remains authoritative. |
| Latitude/longitude, accuracy and location capture time | Optional, foreground and purpose-specific | Untrusted corroboration only; precise values are sensitive and excluded from ordinary lists, notifications and broad exports. |
| Location permission result | Optional bounded enum | Record granted/denied/unavailable/not requested; never store OS internals. |
| Device/client context | Optional and allow-listed | No stable hardware identifier, advertising ID, contact/network inventory or authentication claim. |
| Photos/documents | Optional, type/size/purpose bounded | DMS-only bytes and immutable versions; strip or suppress unapproved EXIF/embedded metadata from ordinary presentation. |
| Worker/person identifiers | Only when a named business purpose and permission require them | Prefer role/membership reference or redacted display; never infer attendance, productivity, payroll or discipline. |
| Sensitive site/security information | Optional and explicitly classified | Separate sensitive permission, private/non-cacheable response where exposed, no notification snippet or cross-Tenant publication. |

Project/site selection is authoritative context but not proof of physical presence.
Location, EXIF, timestamps and device metadata are evidentiary claims. Absence,
denial or mismatch is visible to review but never becomes automatic fraud,
attendance, payroll, site-entry or rejection evidence.

### 3.2 Propagation rule

Downstream P9 surfaces receive references plus minimum necessary display
snapshots, not source payload copies. HSE/QA, Partner, Support and Knowledge must
re-check source permission before showing protected details. Knowledge candidates
may retain approved derivative text and exact source pins; publication manifests,
recurrence and reuse records must not copy precise location, worker identifiers,
diagnostic payloads, private attachment metadata or sensitive site details.

Platform promotion freezes only the sanitized derivative and disclosure evidence.
It must not expose the source Tenant, private source object, restricted DMS pin or
source payload to another Tenant. The Tenant source remains Tenant-owned.

## 4. Evidence-integrity contract

Every P9 evidence binding must identify its owning Tenant, registered source type,
source UUID, exact source revision/version or immutable state token where the
source provides one, exact `Document` and `DocumentVersion` where applicable,
pinned SHA-256, linking actor/time/purpose, and correction/replacement lineage.
DMS remains the only byte authority.

| Later source condition | Required derived-record behavior |
| --- | --- |
| Source corrected or replaced | Preserve the old exact pin. New use requires the successor source/version and, where applicable, a new reviewed candidate/assertion. Never float the old pin. |
| Source superseded | Historical derived evidence remains reproducible; current-use views show the superseded warning and successor link when authorized. No automatic derived supersession. |
| Source withdrawn, invalidated or revoked | Preserve history and mark current eligibility unavailable or warned according to the consuming contract. No deletion and no automatic downstream transition. |
| DMS version becomes inaccessible under current authorization | Deny content access while retaining opaque historical identity/hash for authorized audit. Do not leak title, filename, preview or bytes. |
| DMS document archived, held or later versioned | Historical exact version/hash remains pinned. Archive/hold policy controls access/disposition; a later version never replaces the pin. |
| Source record is absent because of an integrity fault | Fail closed for new consequential use, record a reconciliation exception without sensitive payload, and preserve the derived historical record. |
| Derived publication already exists | Publication remains immutable and historical. Correction, successor, supersession or withdrawal requires its accepted Knowledge lifecycle; source change alone never rewrites it. |

Hashes prove equality/integrity of recorded content, not truth, legal authority,
physical presence or review quality. Ordinary business deletion must not remove
finalized P9 evidence. Any legally authorized disposal remains a DMS/Tenant
retention operation with legal-hold protection and non-fabricated audit evidence.

## 5. Cross-domain consistency matrix

| Domain/evidence | Exact source/version | Hash | Immutable history/correction | Sensitive access | Tenant/DMS boundary |
| --- | --- | --- | --- | --- | --- |
| Field observation/evidence | Observation revision/state plus exact DMS version | Canonical observation and DMS SHA-256 | Submitted/final states immutable; linked successor | Precise location/person/site/media details minimized and separately controlled | Tenant/project/site enforced; DMS owns bytes |
| Compliance evidence | Typed control record/version plus exact DMS version | Rule/result snapshots and DMS SHA-256 | Reinspection/retest, invalidation, NCR/CAPA and reopen append history | Domain object plus sensitive-evidence permission | Profile retains authority; DMS owns bytes |
| Partner evidence/evaluation | Exact qualification/evaluation/source and DMS version | Evidence SHA-256 and deterministic explanation hash | Approved/published facts immutable; replacement/appeal linked | Separate sensitive evidence/export scope | Tenant-local party/profile; DMS owns bytes |
| Support evidence/diagnostics | Case/event/consent/access proposal and exact DMS version | DMS SHA-256 and operation payload identity | Closure correction/reopen/access revoke append history | Explicit diagnostic consent, evidence permission and purpose/scope | Tenant case authority; Platform role alone grants no Tenant access |
| Knowledge provenance | Exact typed source/status/version and optional DMS version | Source manifest/publication hash and DMS SHA-256 | Submitted revisions/publications immutable; successor/supersession/withdrawal | History plus sensitive-provenance permission | Tenant/Platform ownership separate; DMS owns bytes |
| Recurrence source | Each distinct qualifying typed source lineage | Deterministic manifest hash | Immutable invalidation/replacement | Re-check every source permission | Tenant-only assertion; no inference or copied payload |
| Reuse evidence | Exact Knowledge publication and consumer version | Immutable operation/business identity | Immutable reversal/replacement | Publication and consumer permissions both required | Same-Tenant unless the separately public Platform artifact is used; private provenance remains hidden |

Compatible semantics do not require a shared polymorphic evidence table or a new
cross-domain service. Each domain keeps its accepted typed relation and service;
S25 supplies common assertions and targeted tests.

## 6. Notification and workflow final review

### 6.1 Notifications

In-app notifications may be created only for an already-authorized user-facing
attention event with a registered source, such as assignment/review attention,
reasoned correction/return, explicit escalation or an existing work-item/due fact.
They must not be created for passive reads, audit events, raw evidence upload,
sensitive provenance access, recurrence detection, reuse viewing, automatic source
status polling or speculative reminders.

Notification payloads contain only source type, opaque public ID, minimized label,
attention reason and safe route. They contain no raw coordinates, worker/person
details, diagnostic text, attachment filename/preview, sensitive site details,
Knowledge private provenance or commercial evaluation payload. Creation and read
state are Tenant/recipient scoped, deduplicated by stable operation/business key,
and source access is revalidated when opening. A missing, cancelled, superseded or
newly inaccessible source leaves a safe unavailable/cancelled attention artifact;
it never reveals cached content or claims delivery/action completion.

Notifications remain non-authoritative. Audit is not notification, and a
notification cannot grant permission, assignment, workflow candidacy, approval or
source access. Email, SMS, push, providers, queues, schedulers and external
messaging remain unauthorized.

### 6.2 Workflow integrity

Consequential P9 services remain domain-owned. Shared Workflow may route a
registered command and create WorkItems, but it cannot mutate P9 state generically.
Every transition must:

1. resolve active Tenant/membership and object scope;
2. require the explicit business permission and current assignment/candidacy when
   workflow is configured;
3. lock and re-read the domain aggregate/current lineage head;
4. validate expected state/version and exact source eligibility;
5. deduplicate the operation key with its canonical payload;
6. enforce the accepted domain-specific SoD inside the transaction; and
7. atomically persist domain state/history and existing audit evidence.

Existing person-level separation remains authoritative: Field creator/submitter
cannot decide the observation; Compliance protects implementer-versus-verifier
and configured critical closure; Partner author/preparer cannot approve/publish;
Support uses pinned policy rather than universal separation; Knowledge author
cannot formally review/approve/publish that revision. S25 does not impose a new
universal three- or four-person rule.

## 7. Knowledge final review and privacy propagation

Knowledge remains a reviewed derivative, never statutory, policy, contractual,
accounting, procurement, compliance-closure, project-control or workflow authority.
The accepted invariants remain:

- source domains own operational truth and DMS owns bytes/versions;
- submitted revisions and published versions are immutable;
- provenance pins exact typed source/version and exact DMS version/hash;
- correction creates a normally reviewed successor; supersession and withdrawal
  preserve history and do not reactivate predecessors;
- recurrence is a deterministic assertion over explicit distinct source lineage,
  not AI, semantic similarity, causation or opaque scoring;
- reuse is immutable typed evidence, not success, effectiveness or permission to
  mutate the consumer;
- Platform promotion freezes a sanitized separate Platform artifact after
  disclosure evidence and independent review/approval; and
- AI generation, embeddings, vectors, RAG, summarization and external search or
  publication are absent and remain unauthorized.

Sensitive attributes may not propagate into publication manifests, recurrence or
reuse payloads merely because the actor can view the source. Candidate text must be
minimum necessary and reviewed. Provenance/history UI resolves protected details
only on demand after both source-domain and Knowledge sensitive-provenance checks.
Exports apply the same dual authorization and filtering. Platform artifacts carry
no private Tenant provenance beyond the explicitly approved sanitized derivative.

## 8. Export and reconciliation contract

S25 authorizes no new general export subsystem. Where an accepted domain already
implements export or reconciliation, the final contract is:

- explicit domain export/reconciliation permission plus object/Tenant scope;
- separate sensitive-evidence/provenance permission where protected fields exist;
- current authorization re-check for every source and DMS reference;
- exact source/version/hash and current/historical status in the manifest;
- explicit withdrawn, superseded, invalidated, replaced or unavailable labels;
- minimum-necessary columns, no hidden source payload, bytes, previews or private
  Platform-promotion provenance;
- audited actor, Tenant, purpose, filter/scope, time and result identity;
- private/non-cacheable browser responses for sensitive exports; and
- no export-side state mutation or authority inference.

If an existing P9 domain lacks an accepted export path, S25 may test and document
that absence. It must not create one implicitly. Broader export/offboarding and
release reconciliation remain P10/platform-governance work.

## 9. Permission and separation review

The accepted permission catalogues are conceptually sufficient for each domain's
consequential lifecycle, sensitive evidence, audit/reconciliation and controlled
export boundaries. S25 must first prove actual registry/default-grant/enforcement
consistency before proposing a new code.

Required invariants are default denial, active membership and Tenant status,
project/site/object scope, distinct Platform versus Tenant authority, separate
sensitive content/provenance access, no role-name authority, and no Admin bypass of
domain SoD. Positions and workflow routes select responsibility but never grant a
business permission.

The only candidate permission gap requiring explicit Product Owner disposition is
minimum-necessary access to raw precise Field location and similarly sensitive
capture metadata. If inspection proves existing sensitive-evidence permissions can
govern it consistently without semantic ambiguity, reuse the owning domain's
permission. Otherwise introduce one narrowly named Field-sensitive-evidence view/
export permission; never treat ordinary observation view as authority for raw
coordinates or protected metadata.

## 10. Audit final review

Use the existing append-only Audit subsystem only. Consequential P9 audit evidence
must identify actor, Tenant/owner scope, registered object/source identity, action,
previous/current state where applicable, reason/disposition, timestamp,
operation/idempotency or correlation context where applicable, exact evidence or
manifest identity, and protected-purpose/scope for diagnostic/support access.

Audit metadata must not copy precise location, diagnostic content, document bytes,
private publication text or other sensitive payload. Source-domain lifecycle
history remains the detailed business record; Audit supplies cross-cutting evidence
and never becomes a notification or parallel workflow store. Missing historical
audit must not be fabricated by migration.

## 11. Migration posture

The recommended S25 baseline requires **no schema migration**. Documentation
reconciliation and focused assurance should proceed first. If an accepted decision
and verified code gap later require a permission row, masking/status field, index or
constraint, the migration must be expand-only, dependency-safe, reversible within
its bounded contract and non-fabricating.

No migration may invent privacy classifications, source versions, integrity
states, notification/read history, workflow transitions, support consent/access,
Knowledge provenance, recurrence/reuse events or audit records. Existing finalized
history and legacy compatibility remain intact. Contraction requires separate
authorization.

## 12. UI hardening contract

S25 permits only hardening of existing P9 screens after a verified gap:

- Persian-first RTL labels and Jalali display over canonical timezone-aware values;
- explicit badges for current, historical, superseded, withdrawn, invalidated,
  revoked and inaccessible evidence states, not color alone;
- masked precise location, person, diagnostic, sensitive site and protected
  provenance values unless separately authorized;
- safe unavailable-source messages without title/filename/snippet leakage;
- exact source/version/hash/history clarity for authorized users;
- permission-aware actions and normal navigation; GET never mutates;
- private/non-cacheable sensitive detail/export responses; and
- accessible keyboard/focus/error behavior and canonical LTR isolation for UUIDs,
  hashes and technical identifiers.

No new UI subsystem, map/geofence, media gallery authority, notification provider,
workflow designer or generic evidence workbench is authorized.

## 13. Cross-domain no-effect boundary

S25 creates no automatic effect in Accounting/GL, Project Cost, AP/AR, Treasury,
Payroll, Inventory, Equipment, Fixed Assets, Procurement award, Contract state,
Compliance closure, Partner qualification or Project state. Evidence, notification,
workflow routing, recurrence and reuse may only retain their already accepted
domain record or inert proposal. The consuming domain independently authorizes and
executes any later action through its ordinary service.

## 14. Findings and mandatory implementation classification

These are decision-preparation findings, not authorization or final defect claims.

| ID | Finding/gap | Classification | Proposed disposition |
| --- | --- | --- | --- |
| `S25-G01` | Active architecture summaries still contain stale “missing/future” labels for accepted Partner and Notification/Support capabilities. | Documentation reconciliation only | Reconcile after S25 decision without changing runtime. |
| `S25-G02` | Cross-domain privacy/integrity rules exist in separate accepted packets but lack one final consistency matrix. | Documentation reconciliation only | This packet supplies the matrix; link it from affected architecture documents after acceptance. |
| `S25-G03` | S01–S24 acceptance was domain-focused; one targeted cross-domain privacy/evidence/workflow regression is still required for S25. | Test/assurance only | Add one PostgreSQL S25 assurance module after authorization. |
| `S25-G04` | Raw precise Field location/capture metadata needs proof of minimum-necessary read/export enforcement distinct from ordinary list access. | Configuration/permission hardening if existing controls suffice; otherwise bounded runtime hardening | Inspect and test first; add at most one narrow permission/masking boundary if proven missing. |
| `S25-G05` | Sensitive field/media metadata, stale/inaccessible evidence and historical-state warnings need cross-domain presentation verification. | Test/assurance only; bounded UI hardening only for proven failures | Do not redesign screens. |
| `S25-G06` | In-app notification payload minimization, deduplication and open-time source authorization need cross-domain verification. | Test/assurance only; bounded runtime defect/hardening only for proven failures | No new channel, job or notification authority. |
| `S25-G07` | Source correction/withdrawal/DMS inaccessibility must never cause silent provenance drift. | Test/assurance only | Preserve pins/history; add warning projection only if a verified gap exists. |
| `S25-G08` | Existing P9 permission codes/default grants/enforcement require final registry and role-name audit. | Test/assurance only; configuration/permission hardening only for a proven mismatch | No speculative permission expansion. |
| `S25-G09` | Consequential audit coverage and sensitive metadata minimization need one cross-domain sample. | Test/assurance only; bounded defect fix only if evidence is absent or leaks payload | Continue the existing Audit subsystem. |
| `S25-G10` | Broader export/offboarding, providers, schedulers, production operations and automated reconciliation are not S25 gaps. | Deferred to P10 or later | Preserve gates. |

## 15. Product Owner decision register

Every material S25 choice is explicit below. Options A are recommended but remain
unaccepted until the Product Owner responds.

| ID / question | Realistic options | Recommended | Rationale | Area |
| --- | --- | --- | --- | --- |
| `P9-F01` What is S25's operating posture? | A cross-domain assurance with only proven bounded hardening; B new privacy/evidence platform; C redesign accepted domains | **A** | Completes final review without duplicating authorities. | All S25 |
| `P9-F02` How is Field personal/device metadata handled? | A allow-listed minimum necessary, optional unless required, never an authority; B retain arbitrary client metadata; C prohibit all context | **A** | Supports evidence while minimizing privacy risk. | Field privacy |
| `P9-F03` How are precise coordinates exposed? | A optional/untrusted, separately authorized and masked from ordinary lists/notifications/exports; B ordinary view access; C authoritative presence | **A** | Preserves P9-D05/D06 and least privilege. | Field privacy/permissions/UI |
| `P9-F04` How are photos/media governed? | A DMS-only exact version/hash, bounded type/size/purpose and minimized metadata; B copy into each domain; C unrestricted uploads | **A** | Retains one byte/security authority. | Field/DMS/privacy |
| `P9-F05` How may person/site/diagnostic attributes reach Knowledge? | A reference/minimum-necessary reviewed derivative only; B copy source payload; C source-view permission implies publication | **A** | Prevents publication as a privacy bypass. | Knowledge/privacy |
| `P9-F06` What happens when source evidence changes? | A preserve exact pin/history and require a new explicit consuming lifecycle for current use; B float to latest; C delete derived evidence | **A** | Prevents provenance drift. | Evidence integrity |
| `P9-F07` What happens when DMS evidence becomes inaccessible? | A deny content, retain opaque identity/hash/history and fail closed for new use; B cache/copy bytes; C erase links | **A** | Separates authorization from historical integrity. | DMS/evidence |
| `P9-F08` How are stale/missing/withdrawn sources shown? | A explicit non-leaking warning/state with no automatic downstream transition; B hide silently; C auto-withdraw every derivative | **A** | Preserves history and domain authority. | Evidence/UI/workflow |
| `P9-F09` Should compatible evidence semantics use a new common store? | A no; retain typed domain records and common assertions/tests; B polymorphic evidence master; C duplicate DMS | **A** | Avoids another authority and risky refactor. | Cross-domain evidence |
| `P9-F10` Which events may notify? | A registered actionable in-app attention events only; B every audit/state event; C external channels | **A** | Notifications stay useful and non-authoritative. | Notifications |
| `P9-F11` What may notification payloads contain? | A opaque source link plus minimized safe label/reason; B cached source content; C attachments/diagnostics | **A** | Prevents notification leakage and stale authority. | Notifications/privacy |
| `P9-F12` How are stale notification sources handled? | A open-time authorization, safe unavailable/cancelled state and retained attention history; B show cached payload; C delete silently | **A** | Denies leaks while preserving evidence. | Notifications/workflow |
| `P9-F13` What final workflow rule applies? | A domain service authority, row lock, expected state, exact retry and accepted domain SoD; B generic workflow mutation; C universal stronger SoD | **A** | Preserves validated boundaries and small-contractor operation. | Workflow integrity |
| `P9-F14` Is a new sensitive permission required? | A reuse unambiguous existing domain permission where sufficient; otherwise one narrow Field-sensitive metadata permission after proof; B ordinary view always; C broad P9 sensitive super-permission | **A** | Adds only the smallest proven control. | Permissions |
| `P9-F15` What export/reconciliation posture applies? | A existing permissioned domain paths only with filtering, exact lineage and audit; B new general export; C unrestricted spreadsheet dump | **A** | Exports cannot bypass privacy. | Export/reconciliation |
| `P9-F16` What audit model applies? | A existing append-only Audit plus domain history and minimized metadata; B second P9 audit store; C log-only evidence | **A** | One authoritative cross-cutting audit mechanism. | Audit |
| `P9-F17` What migration posture applies? | A no baseline schema change; expand-only/non-fabricating migration only for a proven accepted hardening gap; B infer/backfill states; C contract existing history | **A** | Avoids fabricated evidence and needless schema. | Migration |
| `P9-F18` What validation/closeout gate applies? | A targeted PostgreSQL cross-domain suite plus clean drift/check/docs before S26; B rerun every P9 suite; C documentation only | **A** | Proportionate assurance of shared risks. | Validation/closeout |

## 16. Focused PostgreSQL S25 validation plan

After, and only after, Product Owner acceptance and bounded authorization, create
one targeted cross-domain module. Reuse existing fixtures/helpers and call accepted
services; do not rerun every prior P9 module unless a failure identifies a concrete
regression boundary.

Representative cases must prove:

1. Tenant B cannot discover Field, Compliance, Partner, Support or Knowledge
   source identities, warnings, notifications, provenance or export rows of Tenant A.
2. Ordinary Field view/list access does not expose raw precise location, protected
   client metadata, person details or sensitive media metadata without the accepted
   permission; allowed access is audited where required.
3. Field/HSE/QA/Partner/Support evidence pins the exact `DocumentVersion` and
   SHA-256; a later DMS version does not alter the pin and no P9 table stores bytes.
4. Source correction, supersession, invalidation, withdrawal, archival or current
   inaccessibility retains immutable historical lineage and fails closed for new
   consequential use without silent provenance drift.
5. Knowledge publication/history reproduces the original manifest; protected
   provenance requires both source-domain and Knowledge permissions; withdrawal or
   successor publication preserves prior history.
6. Platform promotion exposes only the frozen sanitized derivative, grants no
   cross-Tenant source/DMS access and leaves the Tenant source unchanged.
7. Recurrence uses explicit distinct authorized source pins only; reuse pins the
   exact publication/consumer; their corrections preserve originals and mutate no
   source/consumer.
8. In-app notifications deduplicate exact retries, reject changed-payload key
   reuse, contain only minimized safe fields, re-check recipient/source access on
   open and handle stale/missing sources without leakage.
9. Representative Field, Compliance, Partner, Support-access and Knowledge
   transitions reject stale state, concurrent conflicting action, unauthorized
   replay, self-approval forbidden by their accepted SoD and role-name-only access.
10. Shared Workflow assignment/candidacy does not grant permission; permission
    alone does not grant assignment where configured; domain state and WorkItem/
    audit completion commit consistently.
11. Consequential audit evidence records actor/Tenant/object/action/state/reason/
    operation context while excluding raw sensitive payload.
12. Existing export/reconciliation paths, if in scope, filter sensitive values,
    label historical/unavailable evidence, remain Tenant-scoped/private and audit
    access; absent paths remain absent.
13. P9 operations create no automatic Project, Procurement, Contract, Compliance
    closure, Partner qualification, cost, financial, Payroll, Inventory, Equipment
    or Fixed Asset effect.
14. Existing Persian RTL/Jalali routes render authorized state/warnings and mask
    protected data; GET is non-mutating and CSRF/POST controls remain active.
15. If a migration is authorized, clean-schema apply plus dependency-safe
    rollback/reapply restores constraints/catalogue without fabricating history.

Run Django system check, migration drift, targeted Ruff/compilation, affected
template loading and URL reversals, stale-claim/link searches and `git diff --check`.
Use one uniquely named disposable PostgreSQL database and one runner; never use
SQLite or a shared test database as acceptance evidence.

## 17. P9-S26 readiness criteria

`P9-S26` may begin only when all of the following are true:

1. `P9-S01–S25 = Product Owner accepted` and this packet records the accepted
   `P9-Fxx` dispositions and exact bounded authorization;
2. every S25 finding is closed as documentation, assurance, accepted bounded
   hardening, or explicit deferral with no unresolved privacy/integrity blocker;
3. no unauthorized cross-Tenant or Platform-to-Tenant source exposure remains;
4. exact source/DMS provenance cannot drift and stale/inaccessible evidence fails
   closed without losing history;
5. no workflow locking, stale-state, retry, SoD or domain/work-item atomicity blocker
   remains in the accepted P9 scope;
6. notification payload/source authorization and sensitive-evidence access pass;
7. the focused PostgreSQL S25 suite and proportionate final checks pass;
8. migration graph is clean; any S25 migration is expand-only, non-fabricating and
   rollback/reapply validated;
9. Roadmap, execution playbook, accepted packets and affected architecture/status
   documents are reconciled; and
10. providers, integrations, AI, downstream/financial effects, production cutover
    and activation gates remain explicit.

S26 is documentation closeout and P10 handoff only. S25 completion cannot grant
P10 runtime or production authority.

## 18. Preserved gates

This packet does not authorize `P9-S26`, P10 runtime, AI-generated Knowledge,
embeddings, vector databases, RAG, semantic inference/summarization, external
search/publication, email/SMS/push providers, queues/schedulers, external
integrations, native/offline expansion, automatic downstream business or financial
effects, production cutover or production activation.

It also does not authorize a shared evidence master, copied DMS bytes, generic
workflow mutation, broader person-level SoD, inferred historical state, automatic
source-to-Knowledge publication, automatic recurrence, or automatic notification
from audit events.

## 19. Exact bounded runtime authorization wording

The Product Owner accepted the following decision text exactly on 2026-10-06:

> Product Owner accepts `P9-F01`–`P9-F18 = Option A` exactly as recorded in the
> `P9-S25 Final Privacy, Evidence and Workflow Review Decision Packet` and
> authorizes implementation and validation of `P9-S25` only. Authorization is
> limited to targeted cross-domain assurance and proven bounded hardening of the
> already accepted P9 runtime: minimum-necessary Field capture metadata; separately
> authorized/masked precise location and sensitive evidence; exact typed source and
> DMS `DocumentVersion`/SHA-256 lineage; non-drifting correction, supersession,
> withdrawal and inaccessible-evidence handling; privacy-minimized source-linked
> in-app notifications with open-time authorization; domain-owned transactional
> workflow integrity and existing SoD; protected Knowledge provenance and sanitized
> Platform promotion; existing permission-scoped export/reconciliation; existing
> append-only Audit evidence; Persian-first RTL/Jalali hardening; and one focused
> PostgreSQL cross-domain assurance suite. Reuse existing domain and DMS authorities;
> add no schema or permission unless a verified gap requires the smallest accepted
> expand-only, non-fabricating change. This authorization does not include
> `P9-S26`, P10 runtime, AI/RAG/vector capabilities, external search/publication,
> email/SMS/push providers, queues/schedulers, integrations, copied document bytes,
> a generic evidence/workflow engine, automatic downstream or financial effects,
> production cutover or production activation. Any departure requires a new
> explicit Product Owner decision.

## 20. Implementation and assurance closeout

`P9-F01`–`P9-F18 = Option A` are accepted. The focused S25 review closed the
findings as follows:

| Finding | Final disposition |
| --- | --- |
| `S25-G01` | Documentation reconciled: stale Partner and Support/Notification status labels were corrected. |
| `S25-G02` | Closed by the cross-domain consistency matrix in this packet and links/status reconciliation in active architecture documents. |
| `S25-G03` | Closed by `tests.test_p9_s25_cross_domain_assurance`: 15/15 focused PostgreSQL cases passed in 1.894 seconds; three directly affected retained cases also passed, for 18/18 in 5.548 seconds. |
| `S25-G04` | Existing `field_observations.location_view` is the unambiguous narrow permission. Lists mask coordinates; detail disclosure is permission-gated and now private/non-cacheable. No new permission was required. |
| `S25-G05` | Cross-domain exact-version/hash/no-byte assertions passed. Sensitive Field, Support and Knowledge history responses were hardened with explicit non-cache controls; stale notification sources render a non-leaking Persian warning. |
| `S25-G06` | Notification creation now requires a registered existing source available to an active recipient, validates exact retry payloads, and revalidates source permission/existence at read time before showing the stored safe label. |
| `S25-G07` | Existing exact `DocumentVersion`/SHA-256 and Knowledge source pins passed focused schema/runtime assertions; no floating pin or history rewrite was found. |
| `S25-G08` | Existing distinct Field, Compliance, Partner, Support and Knowledge sensitive permissions were present and registered; no catalogue/default-grant change was required. |
| `S25-G09` | Representative notification audit evidence remained append-only and payload-minimized; no sensitive summary/location content was copied into audit metadata. |
| `S25-G10` | Remains explicitly deferred: no provider, scheduler, general export/offboarding, automated reconciliation, AI or production capability was added. |

The clean disposable PostgreSQL database
`p9_s25_assurance_20261006_a7f3c1` was migrated from empty through the current
graph. The final focused run passed 18/18 tests. Django system check,
`makemigrations --check --dry-run`, targeted Ruff check/format, template loading,
URL reverse, compilation and whitespace checks passed. The disposable database was
removed after validation.

Validation-process exception: before the controlled disposable-database run, one
misconfigured test invocation selected the pre-existing `test_construction_erp`
database and was interrupted during migration before any S25 test executed. That
database was not used as acceptance evidence and was not subsequently inspected,
cleaned or reused. Its pre-existing/partial state therefore remains outside this
closeout and requires an explicit owner disposition before reuse.

**P9-S25 introduced no schema migration.** No rollback/reapply was therefore
applicable. No Field, Compliance, Partner, Support, Knowledge or downstream source
record was inferred or backfilled.

No automatic effect was introduced in Accounting/GL, Project Cost, AP/AR,
Treasury, Payroll, Inventory, Equipment, Fixed Assets, Procurement award,
Contracts/Claims, Compliance closure, Partner Qualification or Project state.

`P9-S25 = Product Owner accepted`.

Product Owner disposition of `test_construction_erp`: **non-authoritative,
excluded from P9 acceptance evidence, preserve and isolate**. Do not drop, reset,
repair, migrate, reuse for P9/P10 acceptance, or terminate unrelated sessions on
that database without a separate environment-maintenance authorization. The
interrupted preliminary migration is not an S25 functional blocker.

### S26 readiness evaluation

All ten S26 readiness gates in section 17 are satisfied: S01–S25 is Product Owner
accepted; G01–G09 are closed and G10 is an accepted deferral; tenant/privacy,
provenance, workflow, notification, focused PostgreSQL, clean migration, and
documentation gates pass; and deferred provider, AI, downstream, cutover and
production gates remain explicit. Future rehearsals must use uniquely named clean
disposable PostgreSQL databases and one runner per database.

This made S26 ready for separate Product Owner authorization. The Product Owner
subsequently authorized the documentation-only S26 closeout, recorded in
`P9_FINAL_ASSURANCE_CLOSEOUT_AND_P10_HANDOFF.md`; P10 runtime remains
unauthorized.
