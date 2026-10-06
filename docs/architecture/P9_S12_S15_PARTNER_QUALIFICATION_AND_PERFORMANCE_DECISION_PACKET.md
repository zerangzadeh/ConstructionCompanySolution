# P9-S12–S15 Partner Qualification and Performance Decision Packet

**Status:** **PRODUCT OWNER ACCEPTED.** `P9-S12–S15 = Product Owner accepted`.
`P9-P01`–`P9-P18 = Option A` remain accepted. Later P9 tranches through S25
are separately Product Owner accepted, and S26 closeout is complete. P10 runtime
remains separately unauthorized.

**Validation closeout (2026-10-06):** focused PostgreSQL module
`apps.partner_qualification.test_p9_s12_s15` passed (`2 passed in 1.528s`). A
single-runner isolated PostgreSQL rehearsal applied the full graph, rolled back
and reapplied `partner_qualification.0001` and `organizations.0102`, and restored
both migration states. Django check, migration-drift, targeted Ruff and
`git diff --check` passed. No downstream data was fabricated or rewritten.

**Prepared:** 2026-10-06  
**Official envelope:** `P9-S12–S15` only  
**Prerequisite:** `P9-S01–S11 = Product Owner accepted` — verified in
`ROADMAP.md`, the P9 execution playbook, and the accepted P9-S01–S05 and
P9-S06–S11 packets.

## 1. Entry boundary and non-goals

The authoritative P9 session map assigns `P9-S12..S15` to **BusinessParty
qualification/performance evidence and explainable evaluation**. This packet does
not include `P9-S16+`; notifications, calendar, support, knowledge publication,
jobs, queues, integrations, offline/native clients, production cutover, and
production activation are outside the envelope.

The runtime, if later authorized, extends the existing tenant-local
`BusinessParty` master. It must not create a supplier, subcontractor, laboratory,
or partner identity master parallel to Parties. Existing Contracts, Procurement,
HSE/QA, Projects/Sites, DMS, Audit, Workforce and Authorization records remain
authoritative for their own facts.

No qualification or evaluation itself may automatically create or modify a
Project Cost actual, Inventory or Equipment fact, Contract/Claim approval,
Procurement decision, Accounting/GL entry, AP/AR record, Treasury/cash movement,
Payroll effect, or production state.

## 2. Exact session decomposition

| Session | Planning responsibility | Required planning output / stop condition |
| --- | --- | --- |
| `P9-S12` | Verify Parties, DMS, Authorization, Audit, Procurement/Contracts, Projects/Sites and accepted HSE/QA sources. Fix ownership, privacy, non-goals and the no-parallel-master rule. | Current/target ownership and source map; no schema or runtime artifact. |
| `P9-S13` | Define tenant-owned qualification profile, capability/category applicability, source-backed requirements, evidence validity/expiry, review/approval/suspension/expiry/replacement and category approval. | Qualification/evidence state machines, DMS contract and fail-closed rule are decision-ready. |
| `P9-S14` | Define project-scoped performance evaluations for delivery, quality, safety and commercial dimensions; source reference policy, explainability, reviewer conflict, correction/appeal and historical snapshot rules. | Evaluation/metric model and separation rules are decision-ready; no opaque score or automatic consumer effect. |
| `P9-S15` | Consolidate permission catalogue, Persian-first RTL workbenches, migration posture, audit/idempotency/concurrency, proposal-only handoffs, focused PostgreSQL acceptance, Product Owner decisions and bounded runtime wording. | One complete decision register is ready for Product Owner disposition; stop before runtime authorization. |

## 3. Ownership and conceptual data flow

| Fact | Authority | Planned partner-domain use | Boundary |
| --- | --- | --- | --- |
| Counterparty identity, roles, contacts, representatives, classifications and restrictions | Parties / `BusinessParty` | Partner profile is an extension keyed to one active tenant-local party. | No duplicate identity or automatic merge. Existing PartyRestriction remains its own explicit restriction authority. |
| Qualification requirements and capability categories | Partner Qualification | Versioned, tenant-controlled applicability configuration assembled from platform-controlled field/type catalogues. | No invented legal, insurance, tax, HSE or technical requirement. Missing applicable rule fails closed. |
| Document/media bytes, versions, confidentiality, retention and legal hold | DMS | Domain-owned typed links pin exact immutable DMS `DocumentVersion` plus hash. | No blobs, copies, previews or document lifecycle in partner storage. |
| Project/site identity and scope | Projects/Sites | Evaluations and project-specific eligibility cite the authoritative project/site. | Partner records never create or alter project status. |
| Contract, procurement and acceptance facts | Contracts / Procurement | Source-linked reference may support an evaluation or proposed eligibility review. | No automatic approved-vendor consumption, award, PO, contract, claim or receipt effect. |
| HSE/QA facts | Accepted Compliance domain | Accepted finding/NCR/CAPA/inspection/test references may be cited only under an explicit source policy. | Compliance remains separate; partner evaluation never reclassifies or closes its records. |
| Audit and permissions | Audit / Organizations | Partner services append audit evidence and use BusinessPermission plus tenant/project/site scope. | No second audit or authorization model. |

### 3.1 Conceptual aggregates

`BusinessParty` (existing) has at most one active PartnerProfile. A profile has
zero or more versioned `QualificationRequirement` applicability records,
`PartnerQualification` submissions/reviews, immutable `PartnerQualificationEvidence`
links, `PartnerCategoryApproval` decisions, `PartnerEvaluation` headers and
immutable `PartnerEvaluationDimension`/source snapshots. A `PartnerEligibilityProposal`
is a source-only, reviewed handoff record; a consumer must independently authorize
and create any later business fact.

All new conceptual records are organization-scoped; project/site scope is optional
only where the fact is genuinely project/site-specific. A project-specific fact
must share its organization and project/site hierarchy with every cited source.

## 4. Planned lifecycle and history rules

### 4.1 Qualification and category approval

`draft -> submitted -> under_review -> approved | returned | rejected`

- `approved -> suspended | expired | superseded | withdrawn` is a reasoned,
  append-only transition; expiry is derived from a pinned validity end, not a
  scheduled mutation.
- A returned submission may become a new draft revision; an approved submission
  is never edited. Correction/replacement is a new linked submission.
- A category approval is derived only from the currently approved, unexpired,
  non-suspended evidence required by its pinned applicability version. If an
  applicable requirement, evidence, source, permission or scope is missing, the
  result is `not_eligible` rather than inferred approval.
- Existing PartyRestriction may independently block a future consumer only where
  that consumer already honors its explicit effect; partner qualification does not
  create new generic blocking semantics.

### 4.2 Performance evaluation

`draft -> submitted -> under_review -> published | returned | withdrawn`

- Published evaluations and dimension/source snapshots are immutable.
- A correction, appeal outcome or supersession creates a new linked evaluation;
  it never rewrites the published one.
- A score, if Product Owner selects scoring, is a transparent deterministic
  calculation from pinned dimensions/weights and source snapshots. A score is
  descriptive evidence only, not an automatic eligibility, procurement, contract
  or finance decision.
- Evaluation source references are classified as direct observation, approved
  source fact, or reviewer attestation. Missing mandatory provenance blocks
  publication.

### 4.3 Proposals and exceptions

An authorized reviewer may create a `PartnerEligibilityProposal` such as “review
category eligibility for procurement.” It records source version/hash, target
domain, payload and review state but has no automatic consumer effect. Consumer
rejection, expiry, replacement or withdrawal is retained as history.

## 5. Permissions, scope and separation of duties

The later runtime must add explicit capability codes, registry resources,
catalogue/default-role data migration, service/view enforcement and focused tests.
Candidate boundaries are:

| Capability | Boundary |
| --- | --- |
| Partner qualification | view; prepare/submit; review/approve; suspend/withdraw/supersede; view sensitive evidence |
| Category eligibility | configure applicability; review/approve/suspend category decision; create source-only proposal |
| Performance | view; draft/submit; review/publish; return/withdraw/supersede; export/reconcile |
| Evidence and assurance | link exact DMS version; sensitive evidence access; audit/reconciliation; controlled export |

All consequential actions re-resolve active membership, tenant status, required
permission, party organization, project/site scope where present, record state and
current assignment inside the transaction. Positions and category labels never
grant permission.

Recommended SoD is narrow: a preparer cannot approve their own qualification
submission; an evaluation author cannot publish their own evaluation; an appeal
reviewer cannot be the subject source-attestor for the same disputed dimension.
No universal creator/subject/reviewer/closer separation is imposed. Existing
protected-operation rules remain stronger where already applicable.

## 6. Evidence, privacy and DMS

Every evidence link records organization, partner subject, evidence purpose,
exact `Document`, exact immutable `DocumentVersion`, recorded hash, source/provenance,
linking actor and time. Later document versions are never substituted.

Evidence is classified through DMS confidentiality and purpose. Sensitive legal,
tax, insurance, compliance or evaluation evidence requires both the scoped domain
object permission and a separate sensitive-evidence permission. Export is scoped,
audited and excludes unavailable/held evidence according to DMS policy. DMS alone
owns bytes, malware/availability state, retention, hold, download and recovery.

## 7. Audit, idempotency, locking and integrity

Create, submit, review, approve, return, reject, suspend, withdraw, expire,
supersede, publish, correct, appeal, evidence-link, export, reconcile and proposal
operations require append-only `AuditEvent` evidence alongside domain lifecycle
events. Records retain actor, server time, prior/new state, reason, source/version
identity and operation/correlation key.

Mutation services use `transaction.atomic()`, `select_for_update()` on the
aggregate and relevant current approval/configuration, and re-check authorization
and SoD while locked. Opaque operation keys are organization/actor/action scoped,
payload-hash bound, replay an exact prior outcome and reject mismatched reuse.
Database constraints enforce tenant-scoped external numbers, one active profile
per party, valid date intervals, source organization/project consistency and
unique version/transition identities.

## 8. Migration and historical-data strategy

Future migrations are expand-only. They may add new partner-owned tables, typed
DMS links, permission catalogue entries and inert compatibility fields where
needed. They must not infer, backfill, convert or reclassify historical party
roles, supplier/subcontractor status, restrictions, insurance/legal evidence,
qualification, approval, project evaluation, score, block, appeal, source link or
downstream effect. Existing PartyRestriction, Contracts, Procurement, Compliance,
Audit and Workflow history remains unchanged.

Any later replacement follows expand -> explicitly approved backfill (if actual
source evidence exists) -> switch -> reconcile -> validate -> separately approved
contract. No ordinary hard delete is allowed for submitted/reviewed/approved or
published history.

## 9. Persian-first RTL operational requirements

The later runtime must provide Persian-first RTL responsive workbenches for partner
profiles, expiring evidence, category decisions, project evaluations, explanation
drill-through, appeals/corrections, audit history and scoped export/reconciliation.
Dates render in Jalali while storage remains timezone-aware/Gregorian as governed
elsewhere; mixed identifiers/hashes use LTR isolation. UI visibility is not
authorization. Mobile support is responsive online-first only; no durable offline
state or native client is authorized.

## 10. Product Owner decision register

| ID | Decision and recommended option | Other realistic options | Consequence | Sessions |
| --- | --- | --- | --- | --- |
| `P9-P01` | **A — extend tenant-local BusinessParty with a single PartnerProfile.** | B separate supplier/subcontractor masters; C platform-global partner identity. | Preserves canonical identity and tenant privacy. | S12–S15 |
| `P9-P02` | **A — profile is optional and role-neutral; role/category applicability is separate.** | B require supplier/subcontractor role; C duplicate profile per role. | Supports one party in several roles without identity duplication. | S12–S13 |
| `P9-P03` | **A — platform-controlled field/type catalogue plus tenant-versioned applicability.** | B unrestricted tenant custom fields; C fixed statutory checklist. | Bounded flexibility without executable configuration or invented law. | S13 |
| `P9-P04` | **A — fail closed for missing applicable requirement, source or valid evidence.** | B warn-only; C assume prior approval. | Eligibility is never inferred. | S13 |
| `P9-P05` | **A — qualification submission/review with immutable approved versions and linked replacement.** | B edit approved record; C delete/recreate without lineage. | Preserves audit and expiry history. | S13 |
| `P9-P06` | **A — category approval is explicit, version-pinned and descriptive until a consumer independently acts.** | B automatic procurement eligibility; C free-text status. | Avoids hidden purchasing effects. | S13–S15 |
| `P9-P07` | **A — expiry is computed from pinned dates; no scheduler changes status.** | B scheduled expiry mutation; C indefinite approval. | Works without jobs and retains source truth. | S13 |
| `P9-P08` | **A — DMS typed exact-version/hash evidence with separate sensitive access.** | B attachment bytes in Partner; C ordinary document access only. | Preserves DMS authority and privacy. | S13–S15 |
| `P9-P09` | **A — project-scoped evaluations with delivery/quality/safety/commercial dimensions and source snapshots.** | B tenant-wide free-text rating only; C automatic source aggregation. | Retains project context and provenance. | S14 |
| `P9-P10` | **A — deterministic explainable score only from pinned dimensions/weights; score remains advisory.** | B opaque composite score; C no score. | Enables drill-through without automated decisions. | S14 |
| `P9-P11` | **A — published evaluation is immutable; correction/appeal creates linked successor.** | B overwrite; C delete/reissue. | Preserves the decision record and dispute history. | S14 |
| `P9-P12` | **A — narrow reviewer separation: preparer/author cannot approve/publish own record.** | B universal four-person separation; C self-approval. | Protects consequential decisions while supporting small contractors. | S13–S14 |
| `P9-P13` | **A — use existing explicit PartyRestriction only as cited context; introduce no new automatic block semantics.** | B qualification auto-blocks transactions; C ignore restrictions. | Preserves existing consumer ownership. | S12–S15 |
| `P9-P14` | **A — source-linked reviewed proposal/handoff only.** | B direct consumer mutation; C no handoff record. | Keeps downstream domains authoritative. | S14–S15 |
| `P9-P15` | **A — append-only audit plus lifecycle events; exact retry and stale-state controls.** | B audit only; C generic workflow mutation. | Retains domain authority and reliable concurrency behavior. | S13–S15 |
| `P9-P16` | **A — no inferred historic partner qualification/performance migration.** | B heuristic conversion; C destructive replacement. | Prevents fabricated compliance/eligibility history. | S15 |
| `P9-P17` | **A — Persian RTL/Jalali responsive web workbenches, no native/offline runtime.** | B desktop-only; C offline/native client. | Meets operational access within accepted platform constraints. | S15 |
| `P9-P18` | **A — focused PostgreSQL acceptance plus bounded migration rollback/reapply when migrations are added.** | B broad suite only; C unit tests only. | Tests tenant, integrity and concurrency risks proportionately. | S15 |

## 11. Focused PostgreSQL acceptance requirements

Runtime acceptance, if authorized, requires focused PostgreSQL evidence for:

1. cross-tenant party/profile/evidence/evaluation denial and active tenant lifecycle;
2. project/site hierarchy and object-scope denial for project-scoped evaluations;
3. explicit permission family denial, narrow SoD and sensitive-evidence denial;
4. requirement/category version pinning, missing-source fail-closed behavior and
   expiry computation without a scheduler;
5. qualification submit/review/approval/suspend/withdraw/supersede immutability;
6. exact DMS document/version/hash pinning, confidentiality/hold behavior and no
   duplicated bytes;
7. evaluation source snapshots, deterministic explainable score, correction/appeal
   successor lineage and immutable published history;
8. locking races, stale-state rejection, exact idempotent replay and mismatched
   operation-key rejection;
9. scoped export/reconciliation and Persian RTL/Jalali navigation/form validation;
10. proposal-only downstream behavior proving no mutation of Projects/Sites,
    Project Cost, Inventory, Equipment, Contracts/Claims, Procurement, Accounting,
    AP/AR, Treasury, Payroll or production state; and
11. clean-schema migration validation, bounded rollback/reapply, Django check,
    migration drift, targeted Ruff, template compilation and diff hygiene.

## 12. Exact bounded runtime authorization wording

> Product Owner authorizes implementation of `P9-S12–S15` only, exactly within
> accepted `P9-P01`–`P9-P18` decisions and this Partner Qualification and
> Performance Decision Packet. Authorization covers tenant-local BusinessParty
> extension, versioned qualification/evidence/category review, project-scoped
> explainable evaluation, exact DMS-version evidence, narrow SoD, explicit
> permissions, Persian-first RTL adapters, expand-only migrations, audit,
> idempotency/concurrency controls, source-only proposals and focused PostgreSQL
> acceptance. It does not authorize `P9-S16+`, notifications, queues/schedulers,
> APIs, external integrations, native/offline clients, knowledge publication,
> production cutover/activation, inferred historical data, or automatic mutation
> of Projects/Sites, Project Cost, Inventory, Equipment, Contracts/Claims,
> Procurement, Accounting/GL, AP/AR, Treasury or Payroll. DMS remains the sole
> byte/version authority, consumer domains remain sole fact authorities, and
> missing legal or technical rules fail closed.

## 13. Product Owner acceptance

Product Owner accepted this bounded implementation and the validation evidence
recorded in this packet. This acceptance preserves `BusinessParty` as the sole
tenant-local partner identity authority, DMS as the sole document-byte/version
authority, and Projects/Sites, Procurement, Contracts and Compliance as authorities
for their own facts. It authorizes no P9-S16+ work or automatic downstream action.
