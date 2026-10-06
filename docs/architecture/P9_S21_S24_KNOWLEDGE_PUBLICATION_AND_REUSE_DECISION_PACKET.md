# P9-S21–S24 Knowledge Publication and Reuse Decision Packet

**Status:** **PRODUCT OWNER ACCEPTED.**  
**Official envelope:** `P9-S21–S24` only.  
**Verified prerequisite:** `P9-S01–S20 = Product Owner accepted`, as recorded in
`ROADMAP.md`, `docs/ROADMAP_EXECUTION_PLAYBOOK.md`, and the four accepted P9
decision packets. This packet authorizes only the bounded runtime described below.
At the time of this tranche's acceptance, `P9-S25+`, production activation,
external publication/search, AI capabilities, providers, queues, schedulers,
integrations, notifications, and downstream business effects remained
unauthorized. S25 was later accepted and S26 closeout later completed under
separate Product Owner authority; the exclusions in this sentence otherwise remain
unchanged.

## 1. Exact session decomposition

The roadmap/playbook supplies one four-session outcome: reviewed knowledge
publication, provenance, recurrence, and reuse evidence. The bounded decomposition
below maps those four named outcomes one-to-one and adds no later P9 responsibility.

| Session | Bounded planning contract | Decision-ready stop condition |
| --- | --- | --- |
| `P9-S21` | Reviewed knowledge candidates and publication: ownership, authority classification, candidate/publication lifecycles, correction, supersession, withdrawal, and publication eligibility. | The publication boundary and state machines are accepted; no schema or runtime begins. |
| `P9-S22` | Provenance and discovery: exact source/version/DMS/hash lineage, privacy and sensitivity controls, Tenant/Platform scope, taxonomy, search/version visibility, permissions and SoD. | Provenance, access, and discovery decisions are accepted; no external search or publication is authorized. |
| `P9-S23` | Recurrence evidence: qualifying sources, explicit recurrence keys/scope, deterministic validation, deduplication, correction, candidate trigger, audit/idempotency/concurrency and no-effect boundary. | Recurrence is reproducible from explicit source lineage and can create only a candidate proposal. |
| `P9-S24` | Reuse evidence: event meanings, consumer lineage, correction, effectiveness boundary, RTL/Jalali UI, migration posture, reconciliation and focused acceptance consolidation. | Reuse is distinguishable from viewing, and the tranche is acceptance-ready; later P9 work required separate authorization. |

## 2. Ownership, authority, and terminology

### 2.1 Authority chain

Source domains remain authoritative for operational facts. DMS remains the sole
authority for document/media bytes and immutable `DocumentVersion` content.
Knowledge owns only the reviewed derivative, its publication versions, audience,
classification, citations, and knowledge-specific lifecycle evidence. Audit owns
append-only cross-cutting audit evidence; Workflow may coordinate an approved
review route but cannot generically alter knowledge or source-domain state.

The chain is:

`raw operational evidence → source-domain reviewed evidence → knowledge candidate
→ reviewed/approved publication version → reusable guidance/reference → explicit
recurrence and reuse evidence`.

Each arrow is explicit and permissioned. Review of operational evidence does not
create a candidate; a candidate does not become authoritative merely by being
submitted; publication does not change the source case; recurrence does not prove
causation; and reuse does not prove effectiveness.

### 2.2 Exact concepts

| Concept | Meaning and owner |
| --- | --- |
| Raw operational evidence | Mutable or unfinalized source-domain fact/evidence. It is ineligible for publication except as a draft citation visibly marked unverified; it cannot support approval. The source domain owns it. |
| Reviewed evidence | Source-domain evidence that reached the source's own review/final state. It remains source truth, not knowledge or policy. |
| Knowledge candidate | Tenant- or Platform-scoped proposal containing an authored derivative, intended audience/classification, and exact source pins. Draft and review-correction states are mutable with revision history. |
| Approved/published knowledge | An immutable publication version approved under this packet, with complete provenance, classification, audience, effective/review dates, and publication evidence. |
| Reusable guidance/template/reference | A published knowledge presentation or controlled copy/reference pattern. A template remains guidance until its owning domain separately approves/creates a business object. |
| Recurrence evidence | A reviewed, reproducible assertion that distinct qualifying source lineages share an approved recurrence key within an explicit scope and period. It is not a root-cause or liability decision. |
| Reuse evidence | An immutable event recording a defined consumer action against an exact publication version. A view is discovery telemetry, not reuse. |
| Superseded/withdrawn knowledge | Historically retained publication whose current-use status ended by a linked successor or reasoned withdrawal. It remains auditable and reproducible but is not offered as current guidance. |

The bounded publication kinds are the roadmap concepts `LessonLearned`,
`BestPractice`, `TechnicalNote`, `Procedure`, `KnowledgeArticle`, and `CaseStudy`.
The type describes the derivative; it does not elevate authority. In particular, a
knowledge `Procedure` is internal controlled guidance, not a formal Tenant,
Platform, statutory, contractual, accounting, compliance, or operational policy.
Project closeout and other source-domain closures may propose a candidate only;
the source domain retains closeout truth and Knowledge performs its own review.

### 2.3 Publication authority classification

This tranche supports three explicit classifications:

1. **Advisory** — contextual information or lesson; no required action.
2. **Recommended practice** — reviewed recommendation; still not mandatory.
3. **Internal controlled guidance** — controlled knowledge for a named audience,
   effective/review dates, and acknowledgement where configured; it remains
   subordinate to the owning domain's approved policy and cannot create a business
   obligation by itself.

Formal policy, statutory/regulatory authority, contract terms, technical approval,
accounting policy, payroll rule, compliance disposition, procurement decision,
partner qualification, or operational control publication is outside
`P9-S21–S24`. A knowledge item may cite such authority but cannot replace it.
National statutory rules, Platform and Tenant policies, Contracts, Procurement,
Compliance, Accounting, Project Controls, Workforce, Inventory, Equipment, Fixed
Assets, and Support retain their existing authority. Promotion to Procedure,
Checklist, System Control, Training, Partner Performance input, or any other
operational object is a proposal to that owning domain and needs separately
authorized ordinary approval.

## 3. Tenant and Platform ownership

Knowledge may be either Tenant-owned or Platform-owned, never ambiguously both.

- Tenant knowledge is organization-scoped. Its candidates, unpublished versions,
  source details, recurrence, reuse, and audit evidence cannot cross Tenant
  boundaries.
- Platform knowledge is separately governed, cannot embed Tenant-private content,
  and is visible only to eligible Tenant audiences under Platform publication
  rules. Platform scope never grants Platform operators implicit access to Tenant
  source objects or DMS versions.
- Tenant-to-Platform promotion is a new Platform candidate, not a scope-field flip.
  It requires explicit Tenant authorization to disclose, minimum-necessary
  redaction/anonymization, a frozen source/publication pin, independent Platform
  review and approval, and a restricted promotion lineage. Other Tenants see only
  the approved Platform derivative, never the originating Tenant identity or
  provenance unless disclosure was explicitly approved.
- Cross-Tenant aggregation, comparison, reputation, or discovery is outside this
  tranche. Revocation of disclosure cannot erase already valid audit history; it
  triggers review/withdrawal of the Platform derivative under recorded policy.

## 4. Provenance architecture

### 4.1 Required lineage

Every candidate revision and publication version must retain, as applicable:

- owner scope (`TENANT` plus organization, or `PLATFORM`);
- typed source domain and typed source object public identifier;
- exact source object version/revision or immutable event identifier;
- source lifecycle state captured at submission and revalidated at approval;
- DMS `Document` and exact immutable `DocumentVersion` identifiers;
- pinned DMS SHA-256 and approved confidentiality/sensitivity metadata;
- author and contributor memberships/Platform actors;
- reviewer, approver, and publisher identities and timestamps;
- candidate revision and immutable publication version number/hash;
- publication/effective/review/expiry dates where applicable;
- predecessor/successor, correction, supersession, withdrawal, and promotion
  lineage; and
- citation purpose and the minimum excerpt/claim derived from each source.

Typed source adapters must be closed and registered; arbitrary table names,
generic foreign keys, URLs, or user-supplied identifiers are not provenance.
Approval fails closed when a required source is missing, no longer eligible,
cross-scope, mismatched to its pinned version/hash, or inaccessible to the
approver. A publication manifest deterministically hashes its approved body,
metadata, citations, audience/classification, and ordered source pins.

Knowledge stores references, hashes, approved metadata, and authored derivative
content only. It never copies DMS bytes or creates an attachment store. Access to a
pinned DMS version is re-authorized by DMS and the source domain at read time;
publication never broadens source-document permission. A published derivative may
show only content explicitly approved for its publication audience.

### 4.2 Source changes

Source correction, supersession, withdrawal, permission change, legal hold, or
retention state does not silently rewrite a publication. It raises a visible
review condition. An authorized reviewer decides to retain with explanation,
supersede, or withdraw. Historical manifests and permitted source pins remain
reproducible under retention/hold rules; loss of current source-view permission
does not authorize disclosure from the knowledge record.

## 5. Candidate and publication lifecycles

### 5.1 Candidate lifecycle

`draft → submitted → in_review → changes_requested → draft`  
`in_review → recommended → approved_for_publication | rejected`  
`submitted|in_review|changes_requested → withdrawn_candidate`

- `draft` and a returned `changes_requested` working revision are mutable; each
  submission freezes an immutable candidate revision and source manifest.
- Submitted/reviewed revisions are immutable. Correction creates a new candidate
  revision linked to the reviewed revision; it does not edit review evidence.
- Review records recommendation, findings, eligibility checks, and reason. Approval
  is a distinct consequential command against an exact recommended revision.
- Rejection and candidate withdrawal retain the record and reason and create no
  publication.

### 5.2 Published knowledge lifecycle

`approved_for_publication → published_current → superseded | withdrawn`  
`published_current → review_due` (visibility flag/state without destroying current
history); `review_due → confirmed_current | superseded | withdrawn`  
`superseded|withdrawn → archived` only as a retention/access disposition, never
deletion.

- The approved revision and every published version are immutable.
- Publication assigns a monotonically increasing version, exact manifest hash,
  publisher, publication time, audience and classification.
- A pre-publication administrative correction returns to a new candidate revision.
  A post-publication correction always creates a successor publication version.
- Supersession links one current version to its approved successor atomically and
  prevents two current versions in the same publication lineage.
- Withdrawal is a reasoned terminal current-use decision. It does not imply that
  the historical content never existed, and it does not silently activate a prior
  version.
- Archival hides eligible historical records from ordinary navigation under
  retention policy; authorized history/audit remains available. Hard deletion of
  submitted candidates, reviews, publications, recurrence, or reuse evidence is
  not an ordinary operation.

## 6. Recurrence evidence

### 6.1 Meaning and qualifying sources

Recurrence is a reviewed claim that **at least two distinct authoritative source
lineages** share the same approved, typed recurrence key within a stated Tenant,
project/site or Platform-eligible scope and time window. A version, correction,
reopen, duplicate report, or superseding record from one lineage counts once.

Eligible families may include repeated issue/finding, support case,
HSE/QA finding or NCR/CAPA source, project/site pattern, partner-performance
evidence, corrective action, or governed evidence category only after its source
adapter and key semantics are explicitly registered. The source domain continues
to decide what each case means. Similar free text, tags alone, statistical
correlation, or an AI/heuristic cluster is not authoritative recurrence.

### 6.2 Recording and correction

The recommended model is an explicit reviewer-created recurrence assertion with a
deterministically validated manifest. The author selects the governed key, scope,
period and exact source lineages; the system validates tenant/scope, eligibility,
distinct lineage, count, duplicates and source pins. This is reproducible without
a scheduler or opaque inference. A policy version may require more than two
sources, but cannot lower the definition below two distinct lineages.

An idempotent `record recurrence` command freezes the manifest/hash, reviewer,
time, result and optional candidate-proposal link. Incorrect evidence is not
edited: an authorized correction creates a replacement or reasoned invalidation
linked to the prior assertion. Source supersession creates a review condition, not
automatic reclassification. A valid recurrence may propose a knowledge candidate;
it can never auto-publish knowledge, reopen/close cases, create CAPA, block a
partner, change a control, notify users, or cause any downstream action.

## 7. Reuse evidence

### 7.1 Event meanings

| Event | Counts as governed reuse? | Meaning |
| --- | --- | --- |
| Viewed/search result opened | **No** | Discovery telemetry only; it must not be reported as adoption or success. |
| Referenced | Yes | Exact publication version cited by an authorized consumer context. |
| Attached by reference | Yes | A typed, non-byte-copy link was associated with a consumer record. |
| Explicitly adopted | Yes | An authorized actor recorded adoption for a named purpose; this does not approve the consumer object. |
| Used as template | Yes | A new draft was initialized from an exact publication version; the consumer domain owns the resulting draft. |
| Cited in decision | Yes | An authorized decision record cites the publication; it is evidence, not the decision authority. |
| Acknowledged | Yes, but not effectiveness | A named user acknowledged receipt/reading of controlled guidance. |
| Feedback/effectiveness assessment | Separate evidence | A reviewed assessment may describe usefulness/outcome; it does not alter the publication or source fact. |

### 7.2 Immutable consumer lineage

Each reuse event pins owner scope, exact publication/version/hash, reuse type,
consumer domain/object/version, actor, time, purpose, and idempotency key/payload
hash. The consumer adapter must be registered and authorize the actor against the
consumer object. Cross-Tenant links are prohibited; Platform publications may be
reused by a Tenant while the reuse record remains Tenant-private.

Reuse recording neither edits the publication nor mutates the consuming object.
Reference/attachment/adoption in the consumer domain requires that domain's
separately authorized command. A mistaken reuse event is corrected by immutable
reversal/replacement evidence; no in-place edit or deletion is allowed. Counts are
rebuildable projections over valid events and must separate views, reuse types,
acknowledgement, feedback, and any later effectiveness measure.

## 8. Discovery and search boundary

- Use existing PostgreSQL permission-scoped search only. External search services,
  vector databases, embeddings, RAG, AI clustering/summarization, and semantic
  inference are excluded.
- Search is owner- and audience-scoped before ranking. Tenant users may see their
  authorized Tenant publications plus eligible Platform publications; never
  another Tenant's candidates, publications, provenance, recurrence, reuse, tags,
  or counts.
- Searchable fields are approved title, abstract/body, controlled knowledge type,
  governed tags/categories, source-domain label, audience, language, effective/
  review dates, and current status. DMS bytes, raw source text, sensitive
  provenance, unpublished bodies, and restricted metadata are excluded from the
  ordinary index.
- Current published versions are the ordinary default. Superseded/withdrawn items
  are excluded from normal results and recommendations, visibly marked in direct
  historical access, and available only with history permission. Unpublished
  search is a separate permissioned reviewer workbench.
- Categories/tags use governed identifiers and versioned definitions; free labels
  may assist drafting but cannot become authoritative recurrence keys.

## 9. Privacy and sensitive-content policy

Publication uses minimum-necessary disclosure and never treats source access as
publication consent. Every candidate declares sensitivity, audience, purpose, and
source disclosure basis. Eligibility is:

| Information class | Publication rule |
| --- | --- |
| Personal information | Prohibited unless necessary, minimized and supported by an approved purpose; anonymize by default and independently review re-identification risk. |
| Commercially sensitive or confidential project/contract data | Tenant-internal restricted publication only after owner review; Platform promotion prohibited unless explicit disclosure authorization and effective anonymization exist. |
| Security-sensitive information, credentials, exploit detail, protected diagnostics | Prohibited from ordinary publication. A separately controlled security process, outside this tranche, is required. Secrets are never stored. |
| Sensitive HSE/QA evidence | Publish only the minimum reviewed derivative; remove personal/medical/witness identifiers and restrict provenance. Exact evidence remains under HSE/QA and DMS permissions. |
| Support-case information | Publish only a sanitized derivative after consent/authority review; diagnostics, tenant identifiers, access details and attachments remain restricted. |
| Legally/contractually restricted or unredactable content | Publication prohibited. A candidate may retain a restricted rejection/eligibility record without exposing the content. |

Redaction/anonymization is a reviewed candidate revision, not destructive editing
of the source. Sensitive publication requires an independent approver and the
`view sensitive provenance` capability for source drill-through. Search snippets,
exports, audit metadata and reuse events must not reveal restricted provenance.
DMS confidentiality, processing availability, retention and legal hold continue to
apply and fail closed.

## 10. Permission catalogue and separation of duties

Each capability requires active Tenant membership and lifecycle, correct owner
scope, object audience/project/site scope where applicable, and a registered
`BusinessPermissionCode` in any later authorized runtime. Platform operations use
the existing separately governed Platform authorization boundary, not a Tenant
role masquerading as Platform authority.

| Proposed capability | Protected operation |
| --- | --- |
| `knowledge.candidates_create` | Create/edit own eligible draft candidate and cite authorized sources. |
| `knowledge.candidates_submit` | Freeze and submit an exact candidate revision. |
| `knowledge.candidates_review` | View unpublished assigned candidates, record review and request correction/recommend/reject. |
| `knowledge.publications_approve` | Approve an exact recommended revision and audience/classification. |
| `knowledge.publications_publish` | Release an approved version; cannot change approved content. |
| `knowledge.publications_view` | View current published knowledge within audience/scope. |
| `knowledge.unpublished_view` | View unpublished/rejected/withdrawn candidate history beyond assigned review. |
| `knowledge.publications_supersede` | Publish a successor and atomically end the predecessor's current status. |
| `knowledge.publications_withdraw` | Reasoned withdrawal of current publication. |
| `knowledge.history_view` | View superseded/withdrawn versions and lifecycle history. |
| `knowledge.sensitive_provenance_view` | Drill into restricted source/DMS provenance, subject also to source/DMS permission. |
| `knowledge.recurrence_record` | Create/review/invalidate or replace recurrence evidence. |
| `knowledge.reuse_record` | Record/reverse a defined reuse event for an authorized consumer context. |
| `knowledge.taxonomy_manage` | Govern knowledge types, categories, tags and recurrence-key definitions. |
| `knowledge.export` | Minimum-necessary scoped export with sensitivity controls. |
| `knowledge.audit_reconcile` | Reconcile manifests, lifecycle, provenance, recurrence and reuse without mutation authority. |
| Platform promotion/publish capability | Separately controlled Platform operation for sanitized Tenant-to-Platform candidate intake and Platform publication; never granted through a Tenant role. |

Required person-level SoD is narrow:

- An author/contributor may respond to review feedback and prepare revisions but
  cannot record the formal review recommendation, approve, or publish the same
  candidate revision.
- A reviewer may also be the approver/publisher when authorized; publication after
  approval is an exact-content release, so a universally separate third person is
  unnecessary.
- The approver may publish the exact approved version. A different publisher may
  do so but cannot alter it.
- Tenant Owner/Admin and Platform Admin receive no self-publication exception.
- Sensitive content and Tenant-to-Platform promotion require an approver
  independent of every author/contributor. They do not require separate reviewer,
  approver and publisher persons unless a later risk policy explicitly does.
- Recurrence and reuse recording need no universal maker-checker because they have
  no downstream effect; candidate publication still receives the independent
  review above, and every recurrence/reuse correction requires reason and audit.
- Default roles deny consequential publication, sensitive provenance, taxonomy,
  Platform promotion and audit/reconciliation unless explicitly granted.

Positions route work but grant no permission. Workflow assignment/candidacy, if
used, is additional to—not a substitute for—business permission and scope.

## 11. Audit, idempotency, and concurrency

Submission, review, approval, publication, withdrawal, supersession, recurrence
recording/correction, reuse recording/reversal, and Platform promotion must:

1. run transactionally and lock/re-read the aggregate and current lineage head;
2. re-check active membership/Platform authority, Tenant status, permission,
   assignment where configured, source eligibility, audience and SoD inside the
   transaction;
3. require expected state/version and reject stale commands;
4. deduplicate a caller-scoped operation key plus canonical payload hash, returning
   the prior result only for an exact retry and rejecting key reuse with a changed
   payload;
5. enforce database uniqueness for publication lineage/version/current head,
   candidate revision, source manifest members, recurrence manifest members, and
   reuse event business identity;
6. atomically persist domain state, immutable lifecycle event, manifest/hash and
   append-only audit evidence; and
7. prevent concurrent double approval/publication, two current successors,
   duplicate recurrence sources, and duplicate reuse events.

Audit records actor, authority/membership, owner scope, operation, prior/new state,
reason, expected/actual version, source/consumer identifiers, manifest hash,
correlation identifier and time without embedding sensitive content. Audit is
evidence, not notification.

## 12. Correction and lineage matrix

| Action | Required treatment |
| --- | --- |
| Draft edit | Mutable only before submission; normal revision timestamp/actor. |
| Review correction | New candidate revision linked to the frozen reviewed revision; prior review remains immutable. |
| Publication correction | New reviewed candidate and successor publication version; never edit the published version. |
| Superseding publication | Atomically publish successor and mark predecessor superseded with reason/lineage. |
| Withdrawal | Reasoned end of current use; retain content, manifest, audit and direct historical visibility controls. |
| Recurrence correction | Immutable invalidation or replacement assertion with new validated manifest. |
| Reuse correction | Immutable reversal/replacement event; projections exclude reversed evidence but retain it historically. |

Historical publication reproduction uses the exact publication manifest and
permitted pinned source/DMS versions, not the latest source or current taxonomy.

## 13. Migration posture

Any later runtime migration is expand-only, reversible within its declared
boundary, and non-fabricating. It may create empty structures, permission catalog
entries/default grants approved by the Product Owner, constraints, and indexes. It
must not infer or backfill historical candidates, publications, candidate reviews,
approvals, publication versions, withdrawals, supersessions, recurrence, reuse,
acknowledgements, feedback, authority classifications, audiences or Platform
promotions. Existing DMS documents/versions, operational evidence, support known
issues, procedures, free-text lessons, tags, or audit entries remain what they are;
none becomes published knowledge by reinterpretation. Legacy fields remain until a
separately approved expand/migrate/switch/validate/contract plan.

## 14. Persian-first RTL/Jalali UI contract

Normal navigation must expose, according to permission:

- candidate list/detail/editor with eligibility, sensitivity, source pins and
  submission validation;
- assigned review queue with immutable revision comparison, provenance readiness,
  correction findings and SoD explanation;
- approval/publication screen showing exact frozen body, manifest/hash, authority
  class, audience, effective/review dates and stale-state errors;
- published catalogue and detail with current-version badge, advisory/controlled
  authority label, source-summary/provenance access, related current knowledge and
  explicit reuse actions;
- provenance/history view with candidate, review, approval, publication,
  supersession, withdrawal and restricted-source events;
- recurrence workbench with key/scope/period, distinct lineage count, duplicate
  explanation and candidate-proposal status;
- reuse evidence and feedback views separated from views/search impressions;
- supersession/withdrawal actions with reason, successor selection and impact
  warning; and
- reconciliation/audit workbench with filters and export boundary.

Screens are Persian-first, RTL, responsive and accessible. Dates display Jalali
with canonical timezone-aware values preserved server-side. Status, authority,
sensitivity and current/historical state cannot rely on color alone. Search and
normal navigation default to current eligible versions; historical and sensitive
provenance access is explicit and audited.

## 15. Downstream no-effect boundary

Publication, recurrence, reuse, acknowledgement, feedback, search, expiry/review
dates, supersession and withdrawal do not automatically approve workflows; mutate
Projects, Procurement, Contracts/Claims, Compliance findings/CAPA, partner
qualification, Support cases, Inventory, Equipment or Fixed Assets; create Project
Cost actuals or Accounting/GL entries; create AP/AR; execute Treasury; change
Payroll; notify users; or invoke an integration. They may create only the
knowledge-domain evidence or proposal explicitly described here. Every consumer
must be separately authorized by its owning domain and use its ordinary service.

## 16. Product Owner decision register

| ID / decision question | Realistic options | Recommended option | Rationale | Sessions |
| --- | --- | --- | --- | --- |
| `P9-K01` What is published knowledge's authority? | **A:** advisory/recommended/controlled-guidance classes, never formal policy; B: one advisory class; C: publication may create formal policy | **A** | Gives useful control labels without usurping statutory, contract, policy or domain authority. | S21–S24 |
| `P9-K02` Who owns operational truth and published derivatives? | **A:** source domains own facts; Knowledge owns reviewed derivatives; B: Knowledge copies/owns source facts | **A** | Prevents a second authority and preserves correction lineage. | S21–S22 |
| `P9-K03` What scopes may own knowledge? | **A:** separate Tenant and Platform ownership; B: Tenant only; C: shared global records | **A** | Supports platform guidance while maintaining hard Tenant isolation. | S21–S24 |
| `P9-K04` How may Tenant knowledge become Platform knowledge? | **A:** explicit disclosure, sanitized new Platform candidate and independent review; B: flip scope; C: automatic aggregation | **A** | Prevents accidental cross-Tenant disclosure. | S21–S22 |
| `P9-K05` What sources qualify for publication approval? | **A:** reviewed/final typed source versions only; B: any draft; C: DMS file alone | **A** | Publication must rest on authoritative, reviewable lineage. | S21–S22 |
| `P9-K06` What provenance is mandatory? | **A:** typed source/version plus exact DMS version/hash and actor/version lineage where applicable; B: free URL/citation; C: latest source only | **A** | Makes every publication reproducible and auditable. | S22 |
| `P9-K07` Where are attachment bytes stored? | **A:** DMS only, with exact pins; B: copy into Knowledge | **A** | Preserves the sole byte/version/security authority. | S22 |
| `P9-K08` When does content become immutable? | **A:** each submitted revision and every publication version; B: publication only; C: never | **A** | Preserves review evidence and blocks approval races. | S21–S22 |
| `P9-K09` How are post-publication corrections made? | **A:** reviewed successor version; B: edit in place; C: delete/recreate | **A** | Keeps published history reproducible. | S21 |
| `P9-K10` How do supersession and withdrawal behave? | **A:** explicit immutable lineage/current-use state; B: hide/delete; C: overwrite prior status | **A** | Retains evidence and prevents stale guidance from appearing current. | S21–S22 |
| `P9-K11` What person-level SoD applies? | **A:** author cannot formally review/approve/publish own revision; reviewer may also approve/publish; B: three distinct people always; C: self-review/publication | **A** | Protects the consequential decision with a two-person minimum without excluding small contractors. | S21–S22 |
| `P9-K12` Do Admin roles bypass publication SoD? | **A:** no; B: Tenant Admin bypass; C: Platform Admin bypass | **A** | Administration is not content authority. | S21–S22 |
| `P9-K13` How is sensitive content handled? | **A:** minimum necessary, redaction/anonymization, independent approval, class prohibitions; B: source permission alone; C: never publish anything sensitive | **A** | Enables bounded learning without bypassing privacy/security. | S21–S22 |
| `P9-K14` What search technology and corpus are authorized? | **A:** permission-scoped PostgreSQL over approved metadata/body; B: external search; C: vectors/semantic AI | **A** | Fits the current stack and excludes unauthorized data movement/inference. | S22 |
| `P9-K15` How are historical versions discovered? | **A:** current by default, explicit permissioned history; B: mix all versions; C: delete old versions | **A** | Avoids stale guidance while preserving auditability. | S22 |
| `P9-K16` What exactly is recurrence? | **A:** reviewed assertion over at least two distinct typed source lineages sharing a governed key/scope/period; B: repeated free-text similarity; C: author opinion without sources | **A** | Provides a testable definition without claiming causation. | S23 |
| `P9-K17` How is recurrence produced? | **A:** explicit source selection with deterministic validation; B: opaque heuristic/AI; C: scheduled automatic action | **A** | Preserves explainability and needs no scheduler. | S23 |
| `P9-K18` How are duplicates/corrections treated? | **A:** one count per source lineage; immutable invalidate/replace; B: count versions/reopens; C: edit assertion | **A** | Prevents inflated recurrence and lost history. | S23 |
| `P9-K19` What may recurrence trigger? | **A:** candidate proposal only; B: auto-publication; C: automatic domain action | **A** | Preserves publication and downstream authority gates. | S23 |
| `P9-K20` What counts as reuse? | **A:** explicit reference/attach/adopt/template/citation/acknowledgement types; viewing excluded; B: every view; C: only template use | **A** | Separates discovery, adoption and effectiveness. | S24 |
| `P9-K21` How is reuse recorded? | **A:** immutable exact publication and typed consumer pins; B: mutable counter; C: publication-only counter without consumer | **A** | Enables audit and rebuildable metrics without mutating either side. | S24 |
| `P9-K22` How are reuse mistakes corrected? | **A:** reasoned reversal/replacement; B: edit/delete | **A** | Preserves event history and accurate projections. | S24 |
| `P9-K23` What may reuse/effectiveness evidence change? | **A:** knowledge evidence/projections only; B: mutate publication rank/content; C: mutate consumer facts | **A** | Downstream action requires separate authorization. | S24 |
| `P9-K24` What migration and acceptance posture applies? | **A:** expand-only/non-fabricating plus focused PostgreSQL and rollback/reapply; B: infer legacy knowledge; C: broad suite only | **A** | Avoids fabricated authority while validating the material boundaries proportionately. | S21–S24 |

## 17. Focused validation and acceptance plan

If and only if the Product Owner later accepts the decisions and exact runtime
wording, the bounded implementation must pass focused PostgreSQL acceptance:

1. Tenant A cannot read, search, cite, review, publish, recur, reuse, export or
   inspect Tenant B records; Platform scope does not bypass Tenant source access.
2. Platform publication/promotion requires its separate authority, explicit Tenant
   disclosure evidence and sanitized derivative; consumers cannot discover source
   Tenant identity or restricted provenance.
3. Every permission denies by default; inactive membership or suspended/cancelled
   Tenant blocks mutation; project/site/audience scope is enforced.
4. Author self-approval/self-publication fails for Owner/Admin/Platform Admin;
   authorized reviewer/approver/publisher combinations and sensitive independent
   approval behave exactly as decided.
5. Candidate submission freezes revision and ordered source manifest. Approval and
   publication fail for missing/wrong source version, changed eligibility,
   inaccessible/cross-Tenant source, wrong DMS version/hash or stale revision.
6. Publication content/metadata/manifest is immutable. Correction creates a
   successor; concurrent successors cannot produce two current versions.
7. Withdrawal/supersession retains reproducible history, excludes the old version
   from ordinary search and never silently restores a predecessor.
8. Sensitive/prohibited content eligibility, redaction review, source/DMS dual
   authorization, search snippets, export and audit metadata fail closed.
9. DMS remains the only byte store; knowledge pins exact `DocumentVersion` and
   SHA-256 and cannot serve bytes independently.
10. Recurrence requires two distinct qualifying lineages, deduplicates versions/
    corrections/reopens, reproduces its manifest, records invalidation/replacement,
    and creates at most an inert candidate proposal.
11. Reuse types pin exact publication and consumer lineage; views do not count;
    retries deduplicate; reversal/replacement preserves history; no referenced or
    consumer record is mutated.
12. Submission, review, approval, publication, supersession, withdrawal,
    recurrence and reuse exact retries return one result; changed-payload key reuse,
    stale state and concurrent conflicting commands fail deterministically.
13. Audit/reconciliation reconstructs lifecycle heads, publication hashes,
    provenance, recurrence and reuse counts without exposing sensitive payloads.
14. Every no-effect boundary is asserted: no workflow approval, source-domain
    mutation, notifications, finance/cost/payroll/stock/asset effect or integration.
15. Persian-first RTL/Jalali catalogue, candidate/review/publication, provenance,
    recurrence, reuse, history and audit screens are reachable through normal
    navigation and retain canonical timezone-aware values/accessibility.
16. A clean-schema migration applies; the bounded knowledge/organization migration
    rollback and reapply succeeds without fabricated history or dependency break.

Run only the focused module, Django system check, targeted Ruff/template checks and
bounded migration rollback/reapply unless a failure or shared-boundary change
demonstrates need for broader validation.

## 18. Preserved gates

This packet does not authorize `P9-S25+`; AI-generated knowledge; AI clustering,
summarization or recommendation; embeddings/vector databases; RAG; external
publication; external search providers; cross-Tenant analytics; notifications;
queues/schedulers; integrations; native/offline clients; formal policy creation;
automatic promotion; automatic downstream action; production cutover; or
production activation. P9-S25 final assurance and P9-S26 closeout/P10 handoff
remain separate future sessions.

## 19. Exact bounded runtime authorization wording

The following is decision text for a future explicit Product Owner response. It is
not authorization merely because it appears in this packet:

> Product Owner accepts `P9-K01`–`P9-K24 = Option A` exactly as recorded in the
> `P9-S21–S24 Knowledge Publication and Reuse Decision Packet` and authorizes
> implementation of `P9-S21–S24` only. Authorization is limited to Tenant- and
> separately Platform-owned reviewed knowledge candidates; immutable publication
> versions; exact typed source and DMS `DocumentVersion`/SHA-256 provenance;
> advisory, recommended-practice and internal-controlled-guidance classifications;
> permission-scoped PostgreSQL discovery; explicit deterministic recurrence
> evidence; immutable typed reuse evidence; the recorded permissions and narrow
> SoD; Persian-first RTL/Jalali operational UI; append-only audit/reconciliation;
> and expand-only, non-fabricating migrations with focused PostgreSQL acceptance.
> Source domains remain authoritative, DMS remains the sole byte authority, formal
> policy is excluded, and recurrence/reuse create no automatic downstream effect.
> This authorization does not include `P9-S25+`, AI-generated knowledge,
> embeddings/vector databases, RAG, semantic inference or summarization, external
> publication/search, cross-Tenant disclosure, notifications, queues/schedulers,
> integrations, automatic business effects, production cutover or production
> activation. Any departure requires a new explicit Product Owner decision.

**Product Owner acceptance (2026-10-06):** `P9-S21–S24 = Product Owner accepted`.
`P9-K01`–`P9-K24 = Option A` and the
section 19 wording are accepted exactly as recorded. The bounded S21–S24 runtime
implementation is complete in the `knowledge` app: linked reviewed publication
correction/supersession and withdrawal, restricted Tenant-to-Platform promotion,
permissioned provenance/history, immutable recurrence/reuse correction, audit and
Persian RTL/Jalali surfaces are present under expand-only migrations. Lightweight
Django, migration-drift, Ruff, template/URL/render and whitespace checks pass.

## 20. Focused PostgreSQL validation closeout

Validation completed on 2026-10-06 against the single disposable PostgreSQL 18.6
database `p9s21s24_validation_20261006_170001`; `test_construction_erp` was not
accessed. The complete migration graph applied from an empty schema. Knowledge
`0001_initial`, Knowledge `0002_knowledge_lifecycle_completion`, and Organizations
`0104_p9_s21_s24_knowledge_permissions` applied successfully without fabricating
history. The fresh and reapplied schema contained all 12 Knowledge tables, 43
foreign keys, 30 unique constraints, 6 check constraints and 53 indexes, with zero
Knowledge facts, 16 Knowledge permissions and 553 unchanged unrelated permissions.

The PostgreSQL-backed focused module `apps.knowledge.test_p9_s21_s24` passed 13
tests in 14.391 seconds. It covers Tenant isolation, lifecycle/SoD, immutable
publication and history, correction/supersession/withdrawal, representative Field,
Compliance, Partner and Support adapters, exact DMS version/hash pinning and
sensitive provenance, independent Platform promotion/privacy, recurrence and reuse
correction, audit, RTL routes/POST/CSRF controls, and downstream no-effects. It
exposed and verified one scoped PostgreSQL defect fix: Platform promotion
publication now locks only the promotion row instead of applying `FOR UPDATE` to a
nullable outer join.

Dependency-safe rollback removed Knowledge `0002` then `0001`, rolled Organizations
back to `0103`, and reapplied Organizations `0104` then Knowledge through `0002`.
All Knowledge schema objects and catalog permissions were restored, zero history
was fabricated, and unrelated permissions remained unchanged. Django system check,
migration-drift check, targeted Ruff, Python compilation, eight Knowledge template
loads, 23 URL reversals and `git diff --check` passed. The disposable database was
removed after validation and its absence confirmed. This packet is the accepted
architecture and implementation contract for `P9-S21–S24`; cumulatively,
`P9-S01–S25 = Product Owner accepted`. S26 closeout is complete under separate
Product Owner authorization; P10 runtime remains unauthorized.
