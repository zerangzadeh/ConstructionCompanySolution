# P9-S01–S05 Field Operations and Paperless Evidence Decision Packet

**Status:** **P9-S01–S05 Product Owner accepted on 2026-10-05.** `P9-D01`–
`P9-D12` remain accepted exactly as option A recorded below. The accepted runtime
implementation is limited to `P9-S01–S05`, subject to this packet's fixed
boundaries and exclusions.

**Prepared:** 2026-10-05

**Official envelope:** `P9-S01–S05`

## 1. Entry gate and authority

The prerequisite `P8-S01–S30 = Product Owner accepted` is verified from all three
current authorities:

- `ROADMAP.md` records the consolidated P8 tranche as Product Owner accepted and
  complete within documented non-production boundaries.
- `docs/ROADMAP_EXECUTION_PLAYBOOK.md` records every P8 session group through
  `P8-S30` as Product Owner accepted.
- `P8_FINAL_ASSURANCE_CLOSEOUT_AND_P9_HANDOFF.md` records the accepted final
  assurance and names `P9-S01–S05` as the official planning-only P9 entry
  envelope.

The Product Owner accepted every option A in section 10 on 2026-10-05. This
authorizes only the bounded `P9-S01–S05` implementation defined here, including
the required models, migrations, permissions, responsive online-first runtime UI,
and focused validation. At that acceptance point it did not authorize
mobile-native runtime, background jobs, queues, external integrations, or later
P9 work; later P9 tranches through S25 were separately accepted.

## 2. Purpose, outcome, and fixed boundary

This is the single authoritative decision packet for the first P9 envelope. It
defines a bounded design for mobile/context-aware field observations, DMS-backed
media and evidence, weak-connectivity behavior, evidence custody and lineage,
review, and reviewed downstream proposals.

The envelope may prepare only these outcomes:

1. a field user records a structured observation in an explicitly selected
   Tenant, project, and, where applicable, site context;
2. any media or document bytes are received, governed, and versioned only by DMS;
3. capture context and integrity evidence are retained without treating device
   claims as authoritative facts;
4. submitted evidence is immutable and can change only by reasoned linked
   correction or replacement;
5. an authorized independent reviewer accepts or rejects the evidence; and
6. accepted evidence may support a separately reviewed proposal to an existing
   domain, whose own service remains the only authority that can create its fact.

The following are outside this envelope: HSE/QA lifecycle design (`P9-S06+`),
operational document-control families, voice/OCR/QR automation, general-purpose
offline synchronization, native mobile applications, device management,
telemetry/geofencing, notifications, AI, and direct creation or finalization of
downstream business facts.

## 3. Exact session decomposition

| Session | Exact planning scope | Required output / stop condition |
| --- | --- | --- |
| `P9-S01` | Verify entry evidence; inventory the existing Daily Reports, Projects/Sites, Identity/Authorization, Audit, workflow, and DMS authorities; fix the scope and non-goals. | Ownership map and current/target boundary are complete. Stop before schema or runtime design. |
| `P9-S02` | Define field-observation identity, evidence metadata, DMS version binding, custody, timestamps, context, integrity evidence, immutability, and correction/replacement lineage. | Evidence contract and custody rules are decision-ready. No model or migration is created. |
| `P9-S03` | Define allowed project/site/manual/device context, consent and minimization, mismatch treatment, online/intermittent-connectivity behavior, idempotency, conflicts, stale context, and upload retry. | Location/privacy and connectivity choices are decision-ready. No client, API, queue, or integration is created. |
| `P9-S04` | Define submission/review/rejection/correction lifecycle, separation, audit evidence, and proposal-only handoffs to existing authoritative domains. | Lifecycle and consumer contracts are decision-ready. No permission or downstream adapter is created. |
| `P9-S05` | Consolidate Product Owner choices, acceptance criteria, risks, deferrals, and the exact future implementation authorization gate; reconcile the roadmap. | One decision register is ready for explicit Product Owner disposition. Stop with all runtime work unauthorized. |

Work may be revisited within these five sessions only to close a decision in this
packet. The envelope must not absorb `P9-S06+` or implementation work.

## 4. Authoritative domain ownership

| Information / behavior | Authority | Field-capture boundary |
| --- | --- | --- |
| Field observation and its structured descriptive payload | Daily Site and Field Operations | Owns the observation, its review state, immutable submitted snapshot, and correction/replacement lineage. It records observations, not another domain's fact. |
| Evidence metadata binding an observation to exact bytes | Field Operations owns the business binding; DMS owns document/version metadata and byte integrity | The binding pins an exact DMS document version and hash. It never copies a blob or infers approval of a later version. |
| Media/document bytes, immutable file versions, processing availability, confidentiality, retention, hold, export, recovery, previews, and derivatives | **DMS alone** | No `MediaAsset`, attachment store, local server copy, or field-specific blob authority may be introduced. Galleries are projections over DMS versions. |
| Project, site, phase, WBS/activity, and their active scope | Projects/Sites and the existing owning project domains | Field capture stores validated references/snapshots needed for history; it cannot create, rename, reactivate, or broaden these authorities. |
| Login user, active organization membership, business permission, and accepted project/site object scope | Identity and Authorization / Organizations | Every read and mutation re-resolves the active Tenant and current authority. A submitted organization identifier, device claim, position, or workforce assignment never grants access. |
| Optional device/client/session context | Field Operations as untrusted capture evidence; Identity remains user/session authority | Device/client metadata is minimized and evidentiary only. It is not authentication, authorization, attendance, or custody proof. |
| Observation review state and decision evidence | Field Operations, coordinated by the shared workflow authority only if later authorized | Workflow may route work; Field Operations retains state invariants and performs transitions atomically. |
| Correction/replacement lineage | Field Operations for observations; DMS for document versions | Neither predecessor is overwritten. An observation successor pins the relevant predecessor and exact DMS versions. |
| Downstream proposal and its source envelope | Field Operations until handed off | It is an immutable, reviewed proposal, never a downstream actual. The receiving domain independently accepts, rejects, or records an acknowledgement. |
| Progress, time, equipment usage, material/Inventory, cost, payroll, contract, procurement, billing, accounting, or other domain facts | The existing respective business domain | Field capture cannot directly create, approve, post, finalize, reverse, or correct any such fact. |

Accounting remains the sole journal authority; Project Cost remains the sole
project-actual authority; Inventory remains the sole stock/custody/valuation
authority; Equipment remains the operational equipment authority; Workforce and
Timekeeping remain the employee/time authorities; Payroll, Contracts,
Procurement, Billing, AP/AR, Treasury, and Fixed Assets retain their accepted
boundaries. A field observation may cite their identities but never becomes a
parallel ledger, register, timesheet, stock movement, usage log, claim, order,
certificate, or contract instruction.

## 5. Evidence identity, custody, and lineage contract

### 5.1 Observation identity and timestamps

Each future observation needs a stable public UUID allocated once and never
reused. Its business identity includes the Tenant, observation UUID, observation
kind from a platform-controlled closed catalogue, authoritative project, optional
site and approved finer context, and lineage identity where it replaces another
observation.

The architecture distinguishes:

- `created_at`: authoritative server receipt/record creation time;
- `captured_at`: client-claimed time of field capture, retained with timezone or
  offset and marked as client-supplied;
- `effective_at` or business date: the date/time to which the observation applies,
  when operationally distinct from capture; and
- `submitted_at`, `reviewed_at`, and proposal/acknowledgement times: authoritative
  server transition times.

The server time is custody evidence; the client capture time is not silently
promoted to authoritative time. Large clock skew is a visible review exception,
not automatically corrected. Organization timezone governs business-date
interpretation, while the original supplied offset is retained.

### 5.2 Minimum structured evidence

A submitted observation must retain:

- stable identity, Tenant, type, title/summary, structured payload version, and
  source/retry identity;
- project plus optional site and allowed manual context;
- creator's user and active membership identity at submission;
- created, captured/effective, and submitted times with provenance;
- optional minimized client/device and geolocation claims under section 6;
- exact DMS `DocumentVersion` references and their recorded SHA-256 values;
- a deterministic canonical snapshot hash covering the submitted structured
  payload, context identities, timestamps, attachment-version identities, and
  predecessor lineage;
- current lifecycle state and append-only transition evidence with actor, time,
  previous/new state, reason, and review disposition; and
- replacement/correction and downstream-proposal lineage.

Hashes are integrity evidence, not proof that a statement is true, that the
device was at a location, or that a person witnessed the event.

### 5.3 DMS binding and custody

Every attachment is first a DMS document/version governed by existing Tenant,
confidentiality, processing, retention, legal-hold, export, recovery, and access
rules. Submission pins the exact immutable version and its SHA-256. A clean and
available processing disposition is required for review or acceptance when DMS
policy requires it; unknown or unsafe content fails closed.

A later DMS version does not alter submitted evidence. Replacing media creates a
new DMS version or document according to DMS rules and a linked successor
observation; it does not rewrite the pinned version. Typed field-evidence links
must follow the accepted DMS domain-link architecture: a real target relation,
closed registry, complete-context authorization, same-Tenant validation, and no
`GenericForeignKey` or arbitrary model-name dispatch.

DMS retention or legal hold governs the bytes. Field Operations may require a
retention classification through an approved policy but cannot delete, dispose,
or bypass a hold. Device-local temporary copies are not system-of-record custody
and must not outlive the minimum client operation if a future client is authorized.

### 5.4 Immutability and replacement

Draft content may be edited. Submission seals the canonical structured snapshot
and its exact evidence bindings. A submitted, in-review, accepted, rejected, or
superseded record is never edited in place or deleted through ordinary business
behavior.

A correction or replacement creates a new draft linked to exactly one predecessor,
states a mandatory reason, copies nothing implicitly, and revalidates all context
and DMS bindings. On acceptance of the successor, the predecessor becomes
`superseded` while remaining readable as history. Chains must be acyclic and have
at most one accepted current successor. Rejection of a proposed successor leaves
the predecessor's prior disposition unchanged.

## 6. Location and capture context

### 6.1 Allowed context and purpose

The following is the maximum location/context data this envelope may propose:

| Data | Requirement | Purpose / trust level |
| --- | --- | --- |
| Active Tenant | Server-resolved, mandatory | Isolation and policy authority; never accepted from the payload as authority. |
| Project | User selects from currently authorized active projects; mandatory | Primary business scope and downstream routing context. |
| Site | Selected from authorized sites of the project when the observation kind requires it; otherwise optional | Site context. Selection is authoritative identity, but not proof of physical presence. |
| Approved finer context | Optional real references such as phase, WBS/activity, work front, or a bounded manual label when the observation kind allows it | Operational description; every real reference must belong to the same Tenant/project/site hierarchy. |
| Manual context note | Optional, length-bounded free text | Explains a location, access issue, or mismatch; it grants no scope and is treated as untrusted input. |
| Device latitude/longitude | Optional, foreground, explicit user action/permission only | Corroborating capture claim. Never required globally and never treated as authoritative project/site assignment or attendance. |
| Reported horizontal accuracy in metres | Required when coordinates are supplied | Makes device location uncertainty visible. Coordinates without usable accuracy remain low-confidence evidence. |
| Device location capture time | Required when coordinates are supplied | Allows freshness/skew review and is retained as client-supplied. |
| Consent/permission result and source | Retain a bounded result such as granted, denied, unavailable, or not requested | Explains why location is present or absent without storing operating-system permission internals. |

The initial envelope does **not** collect continuous/background location, route
history, altitude, speed, heading, Wi-Fi/cell identifiers, nearby devices,
contacts, advertising identifiers, raw EXIF beyond approved minimized fields, or
a stable hardware identifier. It does not infer attendance, productivity, payroll,
discipline, site entry, or personal movement from location.

### 6.2 Consent, mismatch, and trust

Device geolocation is optional and purpose-specific. The user must see why it is
requested and may continue with manual project/site context when policy permits.
Denial or technical unavailability is not silently represented as zero, current
position, or a failed observation.

The server compares a supplied coordinate only with an approved project/site
location boundary if such boundary data and tolerance later have an explicitly
authorized source. A mismatch, low accuracy, stale fix, impossible clock relation,
or missing location creates a review flag and requires explanation where policy
demands it. It does not auto-reassign the site, grant access, establish fraud, or
automatically reject evidence.

Device coordinates, EXIF, manual descriptions, and network-derived location are
spoofable/untrusted claims. Reviewers see provenance and accuracy. Any later
geofence enforcement, anti-spoofing, device attestation, or telemetry requires a
separate privacy, reliability, false-positive, retention, and appeal decision.

Access to precise location must be separately minimized in future permissions and
exports; list views should prefer the declared project/site and a mismatch flag,
not raw coordinates. Retention must follow the shortest approved business/legal
need and Tenant export/offboarding rules.

## 7. Connectivity, synchronization, and upload model

### 7.1 Recommended first-release boundary

The recommended first release is a responsive, online-first web flow using the
existing Django stack. Server-side drafts are available whenever connected. It
does not include a native app, service worker data store, persistent offline
database, background synchronization, or general bidirectional sync engine.

Intermittent connectivity is handled by explicit connection/saving/upload state,
small independent saves, stable retry identities, and safe retry after a timeout.
The client may preserve unsent values only in the active page's memory for the
short interaction; it must not persist sensitive drafts to browser storage under
this recommendation. A future durable offline draft is a separate choice with
device-loss, encryption, logout/tenant-switch purge, retention, quota, schema
migration, and conflict requirements.

No queue, background job, push channel, or new infrastructure is justified for
this initial boundary. DMS receipt and observation transitions remain synchronous
unless a later implementation packet proves a specific existing asynchronous
need and receives authorization.

### 7.2 Idempotency and duplicate prevention

Every create, draft save, submit, attachment receipt, review decision, correction,
and downstream-proposal command needs a client-generated opaque operation key.
The service scopes it to the Tenant, authenticated actor/session purpose, command
type, and target; an identical retry returns the original result, while reuse with
a different canonical payload fails closed. Database uniqueness, transaction
locking, and deterministic payload fingerprints—not timing or filenames—enforce
this contract.

A content hash may identify identical bytes for review or storage policy, but it
does not by itself prove that two observations are duplicates. User-confirmed
intent and operation identity remain distinct from byte equality.

### 7.3 Conflict and stale-context behavior

Draft saves use an explicit server revision/version token. A stale update is
rejected with the current revision and a human-readable comparison; the server
does not silently apply last-write-wins or merge structured fields. Submitted
records never participate in draft merges.

At every save, upload binding, submission, review, and proposal transition, the
service re-resolves active Tenant status, membership, permission, project/site
scope, target activity, and attachment availability. A deactivated site, revoked
scope, changed project context, archived reference, expired session, or Tenant
switch marks the draft stale and blocks transition until the user reselects valid
context or an authorized reviewer disposes of it. Historic submitted context is
retained even when a source is later archived.

### 7.4 Failed uploads and retry

Media upload is a distinct DMS receipt operation with its own idempotency key,
declared size/type limits, streaming hash/validation, and visible states such as
`not started`, `uploading`, `received/processing`, `available`, and `failed`.
Failure cannot create a submitted attachment binding. Retrying the same operation
must not create a second DMS version; a deliberately different file needs a new
operation key.

The first release should use bounded synchronous uploads and ordinary retry. A
resumable/chunked protocol, background upload, or object-storage direct upload is
not authorized by this packet and requires evidence that the selected media limits
and field connectivity cannot be served safely without it.

## 8. Review, correction, and proposal lifecycle

### 8.1 Observation states and transitions

| State | Meaning | Allowed next action |
| --- | --- | --- |
| `draft` | Editable, incomplete working record; not evidence accepted for business use | save, discard under an approved draft-retention rule, or submit |
| `submitted` | Immutable snapshot and exact DMS bindings sealed; awaiting claim by a reviewer | begin review |
| `in_review` | Immutable evidence is assigned/claimed for an authorized decision | accept or reject |
| `accepted` | Reviewer found the evidence admissible for its declared purpose | prepare a separate downstream proposal or create a linked correction |
| `rejected` | Reviewer rejected admissibility with a mandatory reason | retain history; optionally create a linked corrected replacement |
| `superseded` | An accepted linked successor replaced the prior accepted observation | history only |

There is no reopen or in-place return-to-draft. A correction after submission is a
new linked record. A user may withdraw an unclaimed submission only if a future
Product Owner decision explicitly adds that transition; it is not part of the
recommended first release.

Submission requires a complete canonical payload, valid current context, all
required DMS versions available under policy, and an idempotency key. Review
locks and re-reads the observation, rechecks authorization and scope inside one
transaction, records the decision and audit evidence atomically, and cannot alter
the submitted payload.

Acceptance means only that the observation is admissible field evidence. It does
not certify legal authenticity, approve a contract instruction, establish payroll
time, record inventory consumption, approve equipment usage, recognize progress,
create cost, support a claim automatically, or post a journal.

### 8.2 Separation and authorization design gate

Future implementation must deny by default and distinguish at least view,
capture/edit-draft, submit, review, view-sensitive-location, prepare-proposal, and
review-proposal actions. These are action families for planning only; no permission
codes or grants are created here.

The final accept/reject reviewer must be an active organization member with the
required business permission and current project/site scope, and must not be the
creator or submitter. Position, workforce assignment, device ownership, candidacy,
or workflow routing never grants permission. If shared workflow is used later,
assignment/candidacy is an additional requirement, not a substitute. Sensitive
location/media access must remain narrower than generic observation access where
needed.

### 8.3 Reviewed downstream proposals

Only an `accepted` current observation may source a proposal. A proposal is a
separate immutable-on-submission envelope with its own UUID, consumer type,
source observation/version/hash, exact DMS evidence references, project/site,
effective time, structured lines, units, actor/time history, payload hash,
idempotency identity, review disposition, and correction/replacement lineage.

The field proposal lifecycle is `draft -> submitted -> reviewed-accepted` or
`reviewed-rejected`; submitted proposals are immutable. Proposal review is
independent of the preparer. Evidence acceptance and proposal acceptance are
separate decisions and may require different reviewers.

The recommended candidate families for a later, explicitly authorized first
implementation are:

1. project progress/physical-work observation proposal;
2. Timekeeping timesheet-entry proposal;
3. Equipment usage proposal; and
4. Inventory material-issue/consumption proposal.

These names describe potential consumer contracts, not authorization to build
them. Each family remains disabled until its owning domain approves an exact
source contract, mappings, units, correction/reversal handling, permissions,
idempotency key, reconciliation, and no-double-count tests. Payroll, claims,
Billing, Accounting, Project Cost actuals, Contracts, Procurement, AP/AR,
Treasury/cash, and Fixed Assets are not direct consumers in this envelope.

The receiving domain alone may create its own draft or fact through its existing
authorized service. It revalidates the Tenant, scope, source state, units, mapping,
duplicate key, and consumer lifecycle. Receipt/acknowledgement is append-only and
does not mutate or elevate the field evidence. Consumer rejection leaves the
source accepted but records a reason. A source correction never silently changes
an already consumed fact; consumer correction/reversal follows that domain's own
authorized lifecycle.

## 9. Media policy alternatives

All alternatives use DMS; none creates a media store.

| Choice | Initial media boundary | Trade-off |
| --- | --- | --- |
| **A — recommended** | Photos and bounded ordinary document evidence only. Video remains planned but deferred until explicit per-file/aggregate limits, processing availability, storage/recovery capacity, preview behavior, privacy, and poor-connectivity evidence are approved. | Lowest first-release infrastructure and custody risk; does not deliver field video initially. |
| B | Photos plus short bounded video through synchronous DMS receipt. | Closer to the target outcome, but requires approved format/size/duration limits and proof that synchronous upload and processing are usable in field conditions. |
| C | Photos, documents, and broad/resumable video with background upload. | Requires additional client/upload infrastructure and operational controls; outside this first-release recommendation. |

Whichever choice is accepted, allowed types, maximum count/size, confidentiality,
EXIF minimization, processing availability, retention classification, previews,
export, and accessibility alternatives must be fixed before implementation.

## 10. Product Owner decision register

The Product Owner explicitly accepted **option A exactly as written** for every
decision on 2026-10-05. No alternative, broadening, or implied consumer activation
is accepted.

| Decision | A — recommended | B / other decision-ready alternative | Status |
| --- | --- | --- | --- |
| `P9-D01` Field boundary | **A accepted:** A dedicated Field Operations observation authority that proposes but never duplicates downstream facts | Extend only Daily Reports and create no general observation authority; document exact coverage gaps | **ACCEPTED — A** |
| `P9-D02` DMS custody | **A accepted:** DMS is the sole byte/version/derivative/retention authority; field binds exact versions/hashes | No conforming parallel-storage alternative | **ACCEPTED — A** |
| `P9-D03` Initial client | **A accepted:** Responsive online-first Django web flow; no native app or persistent offline store | Authorize a separately bounded client/offline architecture and its security/operations gates | **ACCEPTED — A** |
| `P9-D04` Offline behavior | **A accepted:** Server drafts plus idempotent retry; active-page transient preservation only; broad/durable offline deferred | Encrypted durable local drafts with an approved device-loss, purge, sync, schema, and conflict contract | **ACCEPTED — A** |
| `P9-D05` Location | **A accepted:** User-selected project/site plus optional foreground coordinates, accuracy, time, and consent result; treat as untrusted corroboration | Manual context only, or a separately justified stricter location policy | **ACCEPTED — A** |
| `P9-D06` Mismatch | **A accepted:** Flag for review and explanation; never auto-reassign or treat as proof/fraud | Approved threshold-based blocking after authoritative site geometry and appeal policy exist | **ACCEPTED — A** |
| `P9-D07` Review lifecycle | **A accepted:** `draft -> submitted -> in_review -> accepted/rejected`, with linked successor correction and supersession | Add explicitly defined withdrawal/return behavior without mutating submitted evidence | **ACCEPTED — A** |
| `P9-D08` Separation | **A accepted:** Creator/submitter cannot accept or reject their own observation; proposal preparation and review are separate | Named, risk-bounded same-user exception with audit and no protected operation | **ACCEPTED — A** |
| `P9-D09` Initial media | **A accepted:** Media choice A in section 9: photos and bounded documents; video deferred behind explicit limits/evidence | Choice B or C with the listed operational approvals | **ACCEPTED — A** |
| `P9-D10` Proposal families | **A accepted:** Prepare contracts for progress, time, equipment usage, and material consumption, but activate none until each consumer separately accepts its contract | Select a narrower named subset; no unnamed/general consumer | **ACCEPTED — A** |
| `P9-D11` Consumption | **A accepted:** Consumer creates its own draft/fact explicitly and acknowledges source; no automatic finalization | No conforming direct-finalization alternative | **ACCEPTED — A** |
| `P9-D12` Submitted retention | **A accepted:** Immutable submitted/review/proposal evidence follows DMS/Tenant retention and legal-hold policy; no ordinary hard delete | A stricter approved retention schedule by evidence class | **ACCEPTED — A** |

The Product Owner acceptance identifies `P9-D01`–`P9-D12`, selects A without
variation, and authorizes the `P9-S01–S05` implementation envelope only.

## 11. Risks and required controls before runtime authorization

| Risk | Required decision/control evidence |
| --- | --- |
| Cross-Tenant or out-of-scope capture/read | Active Tenant resolution, object-scope query/service tests, same-Tenant relations, negative list/detail/upload/export tests |
| DMS bypass or ambiguous bytes | Exact immutable version/hash binding, clean-processing gate, typed registered link, no alternate blob path |
| False confidence in GPS/device time | Provenance and accuracy display, mismatch flag, optional consent, no authority or automated adverse inference |
| Duplicate retry or double consumption | Command-scoped idempotency, payload fingerprint, database uniqueness/locks, consumer source uniqueness and reconciliation |
| Lost/conflicting drafts | Explicit save state, revision token, stale rejection and user comparison; no silent merge/last-write-wins |
| Changed/revoked context | Re-resolve membership, Tenant, project/site and references on every command; block stale drafts while preserving submitted history |
| Evidence tampering or silent correction | Canonical snapshot hash, immutable submitted payload, append-only transitions, linked acyclic replacement |
| Media privacy or device residue | Data minimization, DMS confidentiality/retention, no persistent local cache in recommended release, export/access audit |
| Downstream authority leakage | Proposal-only contract, independent review, consumer-owned command, acknowledgement and no-double-count/correction tests |
| Unnecessary infrastructure | Online-first synchronous path; queue, resumable upload, native client and general sync require measured evidence and separate authorization |

## 12. Acceptance criteria for this planning envelope

`P9-S01–S05` planning is ready for Product Owner disposition when:

1. the Product Owner records an explicit disposition for `P9-D01`–`P9-D12`;
2. domain owners confirm DMS, Projects/Sites, Identity/Authorization, workflow, and
   every selected consumer boundary without transferring authority;
3. the selected media formats/limits, location retention/access, draft retention,
   and any offline boundary are concrete rather than placeholders;
4. each selected downstream family has a named owner and remains disabled until a
   separate consumer contract is accepted;
5. future implementation acceptance tests are required to cover Tenant and object
   isolation, DMS binding/availability, immutability, correction lineage,
   separation, idempotent retry, stale context, upload failure, conflict, privacy,
   consumer rejection, and no downstream side effect; and
6. a new, exact Product Owner authorization names the sessions and artifacts that
   may be implemented.

The Product Owner has accepted the planning decisions and authorized bounded
`P9-S01–S05` runtime implementation. This authorization does not extend to
background jobs, queues, integrations, consumer adapters that create domain facts,
or `P9-S06+`.

## 13. Explicit deferrals

- native mobile applications, installable offline clients, persistent local data,
  general synchronization, background upload, and device management;
- video unless `P9-D09` explicitly selects it with concrete limits and operational
  controls;
- GPS/geofence enforcement, live tracking, telemetry, device attestation, or
  attendance/productivity inference;
- voice transcription, OCR-derived field values, barcode/QR automation, and AI;
- HSE/QA, partner, notification/support, knowledge, and all `P9-S06+` scope;
- transmittal/RFI/submittal/method-statement/drawing business lifecycles;
- automatic downstream creation/finalization, financial recognition, stock
  mutation, contract effect, payroll effect, billing/claim effect, journal posting,
  or Project Cost actual creation; and
- production activation, provider selection, queueing, or external integration.

These deferrals preserve roadmap targets; they are not implementation authority.

## 14. Bounded implementation record

**Implementation delivery and Product Owner acceptance (2026-10-05):** the
Product Owner accepts the implemented `P9-S01–S05` runtime and its validation
evidence. Acceptance covers the fixed scope in this packet, including
tenant/project/site-scoped observations, immutable review/correction lineage,
DMS-only evidence custody with pinned version/hash evidence, minimized/untrusted
location, scoped permissions, RTL UI, idempotency/audit integrity, and source-only
downstream proposals. It does not broaden the accepted scope or authorize
`P9-S06+`.

- Field Operations adds tenant/project/site-scoped `FieldObservation` records,
  draft revision and status history, correction/supersession lineage, explicit
  field permissions, default-denied role grants, audit actions, and responsive
  online-first Django views.
- A field-evidence binding pins one available DMS `DocumentVersion` and its hash.
  DMS remains the only byte/version store; submitted and reviewed observations
  reject any new DMS attachment.
- Optional location is captured only with the approved permission/accuracy/time
  labels, is deliberately untrusted, and precise display remains separately
  permissioned. No device-resident draft store, queue, worker, integration,
  native client, video path, or generalized synchronization is present.
- Accepted evidence may create only the approved source-only proposal envelopes
  for progress, time, equipment usage, or material consumption. No consumer
  command or business/financial fact is invoked.

**Validation record (2026-10-05):** an isolated PostgreSQL 18.6 clean schema
completed the complete historical migration graph with one process and no stale
process, lock contention, or migration error. The reusable PostgreSQL focused
module then passed **6 tests**: tenant and project/site scope, capture/review
permissions, immutable submission/correction lineage, DMS version/hash pinning,
post-submission attachment blocking, minimized/untrusted location, source-only
proposals, and RTL workbench access. `daily_reports.0005` and its dependent
`0006` were rolled back to `0004` and reapplied successfully; the PostgreSQL
catalog confirmed the P9 tables, indexes, constraints, and foreign keys. Django
checks, migration-drift, targeted Ruff, template compilation, and `git diff
--check` pass. Two scoped PostgreSQL defects were corrected during this evidence
pass: locking only the observation/proposal row across nullable context joins,
and re-reading field-observation state in the DMS attachment guard. The Product
Owner accepts this bounded implementation and validation evidence. The full
application suite was intentionally not run and is not required for this tranche;
this acceptance remains neither authorization for `P9-S06+` nor production
activation.
