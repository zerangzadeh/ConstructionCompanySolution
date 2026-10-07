# P10-S14–S17 Project Closeout Coordination Decision Packet

**Status:** **P10-S14–S17 Product Owner accepted.**

**Date:** 2026-10-07.

**Verified prerequisite:** `P10-S02–S13 = Product Owner accepted`.

**Authority:** this is the single authoritative Product Owner decision packet for
`P10-S14–S17`. It is governed by `ROADMAP.md`, the P10 session map in
`docs/ROADMAP_EXECUTION_PLAYBOOK.md`, the accepted P10 S01–S06 and S07–S13
decision packets, and the directly affected domain, data, capability, workflow,
permission, user-capability and UI authorities cited here. Models, migrations and
tests remain authoritative for current runtime behavior.

**Current effect:** on 2026-10-07 the Product Owner accepted
`P10-C01`–`P10-C36 = Option A` and supplied the exact bounded wording in section
16, authorizing implementation of P10-S14–S17 only. The Product Owner has now
accepted P10-S14–S17 and its recorded validation evidence. `P10-S18+` remains
outside this packet and requires separate Product Owner decisions and
authorization.

## 1. Entry gate and bounded outcome

The entry gate is satisfied: the Product Owner accepted P10-S02–S13, including
six governed metrics, 13 governed reconciliation pairs, immutable lineage,
explicit non-value states, permission-preserving drill-through and successor-only
recalculation.

The completed envelope was exactly **P10-S14–S17**. Its purpose was a
Tenant-scoped **project-closeout coordination and acceptance control** over
authoritative facts already owned by Projects/Project Controls, Contracts,
Billing, DMS, Inventory, Equipment, Fixed Assets, Field/HSE/QA, Knowledge,
Reporting and Reconciliation. It is not a generic closeout engine and does not
create a new balance, document store, workflow, source lifecycle or project-status
authority.

The controlling rule is:

> Source domains remain authoritative. Reporting owns only a versioned closeout
> control profile, immutable assessments/snapshots, coordination history and
> governed closeout-acceptance evidence. A Reporting acceptance means that the
> pinned control profile was assessed and accepted at a stated cutoff; it does
> not close, approve, settle, dispose, publish, post, reverse or mutate any source
> record, project lifecycle, contract, claim, document, asset, stock position,
> reconciliation, financial period or knowledge publication.

Unknown, inaccessible, incomplete, stale, gated and not-applicable facts remain
distinct. None becomes a fabricated zero, a synthetic completion, or an implied
domain approval.

## 2. Exact S14–S17 decomposition

| Session | Exact bounded outcome | Entry and stop condition |
| --- | --- | --- |
| `P10-S14` | Closeout foundation: code-governed profile/version catalogue, exact control families and source-authority registry; Tenant/project-scoped closeout case and immutable source-manifest/assessment schema; new default-deny permission catalogue | Requires `P10-C01`–`P10-C36` acceptance and named Product Owner acceptance owner. Stop if a control lacks an authoritative source, deterministic status/cutoff contract or object-scope rule. |
| `P10-S15` | Explicit synchronous capture and assessment of the authorized control families, including freshness/staleness, coverage, unknown/incomplete/gated states, immutable item snapshots and proposal-only requests for source-owner action | No source mutation, automatic completion, scheduled refresh, workflow duplication or financial/project-status effect. Stop rather than infer from mutable labels, absent records or legacy zero/default fields. |
| `P10-S16` | Append-only coordination, review, acceptance/rejection, reopen and successor-assessment evidence; Persian-first RTL/Jalali workbench, permission-preserving drill-through, privacy/masking, exact DMS pins and bounded on-demand closeout export | Independent acceptor differs from preparer and last material disposer. Accepted evidence is immutable. No project/contract/period close, document publication, asset/material disposal or downstream execution. |
| `P10-S17` | Focused PostgreSQL acceptance; clean-schema migration plus bounded rollback/reapply; authority, isolation, concurrency, history, export and no-effect assurance; documentation closeout and bounded S18 handoff preparation only | **Product Owner accepted.** The next official envelope is P10-S18–S21 and requires separate Product Owner decisions and authorization. No S18 work, production certification or activation begins from this acceptance. |

S14–S17 is one proposed runtime tranche. A partial subset is not a certified
project closeout and may be described as accepted only if the Product Owner names
the subset and its focused acceptance criteria pass.

## 3. Ownership and source-authority model

### 3.1 Reporting-owned control evidence

Reporting may own only:

- a code-governed closeout profile identity and immutable versions defining the
  required control families, registered source adapters, statuses, cutoff,
  freshness, materiality, sensitivity and acceptance rules;
- a Tenant/project-scoped closeout case, immutable assessment runs, source
  manifests/watermarks, item snapshots, fingerprints and coverage evidence;
- append-only coordination notes, assignee history, source-action proposals,
  source-correction references, review, acceptance/rejection and reopen events;
- successor relationships and current pointers that never rewrite accepted
  history; and
- byte-free export manifests plus exact DMS `DocumentVersion`/hash references.

Reporting does **not** own project completion, contract closeout, commercial
entitlement, claim/certificate status, settlement, document completeness facts,
asset or material disposition, HSE/QA closure, knowledge publication, metric or
reconciliation source results, journal/period status, or source correction.

### 3.2 Authorized control families and source authorities

| Control family | Authoritative facts | What P10 may record | Explicit boundary |
| --- | --- | --- | --- |
| Project identity and scope | Projects owns Organization/project/site identity and its ordinary lifecycle; Project Controls owns WBS/CBS, schedule, budget, forecast and control evidence | Exact project/scope/cutoff pins and a derived closeout assessment | P10 cannot change project status, schedule, budget, forecast, WBS/CBS or acceptance policy. |
| Contract/commercial obligations | Contracts owns contract/term/amendment, guarantee, clearance, Site Instruction, Variation/Change Order, contractual Claim and EOT facts | Counts/statuses, exact source versions and unresolved-control evidence | P10 acceptance is not contract closure, entitlement, variation approval, release or Article 38 interpretation. |
| Billing, claims and settlement | Billing owns receivable claims/payable certificates and corrections; AP/AR owns obligations/allocations; Treasury owns cash; Accounting owns journals | Exact current/final source states and existing reconciliation/settlement evidence | No claim certification, AP/AR recognition, settlement, write-off, cash action, journal or period effect. |
| Reconciliation and performance | P10 S02–S13 owns its immutable metric/reconciliation control evidence; native domains retain native reconciliation authority | Pin accepted/current result versions, freshness and unresolved exceptions | S14–S17 cannot rerun, close or reinterpret a reconciliation or replace native sign-off. |
| DMS/document completeness | DMS owns `Document`/immutable `DocumentVersion`, retention, classification and bytes; each source domain owns whether its required evidence is satisfied | A profile-defined completeness assessment with exact version/hash pins and visible unavailable/redacted states | P10 cannot upload a substitute, publish, approve, archive, delete, waive retention or claim legal completeness outside the source rule. |
| Inventory/material disposition | Inventory owns quantity, reservation, custody, traceability, count, transfer and valuation evidence | Pin authoritative disposition/status evidence and any unresolved exception | No stock posting/reversal, transfer, reservation release, valuation, disposal or downstream proposal consumption. |
| Equipment and Fixed Assets | Equipment owns operations/maintenance and proposals; Fixed Assets owns capitalization/book/depreciation/impairment/transfer/disposal evidence | Pin source-backed state and reconciliation/proposal evidence | No maintenance completion, asset disposal, depreciation, journal or Project Cost actual. |
| Field, HSE and QA issues | Field Operations, HSE and Quality own observations, incidents/issues, inspections, permits, NCR/CAPA and their closure/correction histories | Pin exact status/version, open-control evidence and profile assessment | No incident/NCR/CAPA closure, verification, waiver, source proposal or evidence mutation. |
| Knowledge and lessons learned | Knowledge owns reviewed publication/version, recurrence and reuse evidence; source domains retain operational truth | Pin a published or explicitly absent/gated reviewed lesson and its provenance | P10 cannot author, sanitize, approve, publish, supersede or infer knowledge from source data. |

A profile version must name each enabled family, authoritative adapter and source
owner. An unavailable or unauthorized family is `gated/unavailable`, not silently
omitted. P10 may not add a family merely because a model/table exists.

### 3.3 Cross-domain action classification

| Interaction | Classification | Rule |
| --- | --- | --- |
| Read exact permitted source status/version | Read | Recheck active Tenant membership, object scope and the source-domain permission at capture and drill-through. |
| Store immutable snapshot, manifest, assessment or acceptance evidence | P10-owned derived/control mutation | Allowed only through a P10 service with atomic audit and no source mutation. |
| Ask a source owner to investigate/correct/complete evidence | Proposal/coordination | Append-only request/reference only; it grants no permission and creates no source work item unless separately authorized through the existing workflow authority. |
| Close/approve/correct a source record | Source-domain mutation | Prohibited through P10. The authorized source-domain service and lifecycle are required. |
| Change project status, release retention, post, pay, dispose, publish or trigger another consumer | Downstream/consequential mutation | Prohibited in S14–S17. |

## 4. Lifecycle and control semantics

### 4.1 Profile and case

Closeout profile version:

`draft -> in_review -> published -> superseded | retired`, with
`draft/in_review -> withdrawn`. A published version is immutable. The author
cannot publish it; affected source owners must review their family contracts.

Closeout case:

`draft -> active -> review_pending -> accepted | rejected`

`draft/active/review_pending -> cancelled` is allowed only before acceptance and
requires reason. `accepted -> reopened` requires a separate permission, reason
and qualifying new/stale/corrected evidence. Reopen is an append-only event and
creates or requires a successor assessment; it never changes the accepted
historical acceptance event. Rejection retains the assessment and may be followed
by a successor assessment after source action.

A closeout case is coordination state only. Its status cannot drive or mirror a
project, contract, accounting period or source-domain lifecycle state.

### 4.2 Assessment and item statuses

Assessment run:

`requested -> capturing -> assessing -> completed | failed | cancelled`.

Cancellation is allowed only before the immutable assessment snapshot is
completed. A completed assessment pins Tenant/project, profile version, cutoff,
Tenant timezone, source adapter versions, ordered manifests/hashes, source states,
coverage, item outcomes, actor/time and calculation fingerprint.

Each control item has exactly one derived outcome:

- `satisfied` — the profile rule is proved by authorized pinned evidence;
- `blocked` — an authoritative source explicitly shows an unresolved condition;
- `unknown` — a required fact cannot be established;
- `incomplete` — expected scope/evidence coverage is partial;
- `stale` — a pinned source or accepted supporting control has a newer relevant
  authoritative version or breached freshness rule;
- `unverifiable` — required retained source/evidence cannot reproduce the result;
- `not_applicable` — a versioned rule and evidence prove exclusion; or
- `gated/unavailable` — the source capability, adapter or access is deliberately
  absent.

Only `satisfied` and policy-proved `not_applicable` can satisfy a control.
`unknown`, `incomplete`, `stale`, `unverifiable` and `gated/unavailable` never
equal zero, complete, waived or satisfied. A profile may require every material
item to be satisfied and may explicitly permit named non-material open items with
accepted residual-risk evidence; it may never waive Tenant/isolation, integrity,
security, missing authority or broken-lineage failures.

### 4.3 Acceptance and evidence meaning

Acceptance pins the completed assessment, all item outcomes, accepted residual
risks, independent acceptor and source-owner acknowledgements required by the
profile. It does not assert facts after the cutoff. New source versions make the
current presentation stale by rule and may require reopen; they do not alter the
historical assessment or acceptance.

Accepted closeout evidence and its item snapshots are immutable governed
evidence. Corrections use source-domain correction/reversal/supersession plus a
new P10 assessment and, when applicable, a successor acceptance. Incorrect P10
metadata is corrected by an append-only correction/supersession event, never by
editing the accepted record.

## 5. Stale state, locking, idempotency and concurrency

- Every consequential command requires a client-observed version or equivalent
  stale-state token and an operation-specific idempotency key scoped to Tenant,
  case, command and actor/purpose.
- Duplicate identical retries return the one authoritative outcome. Reuse of a
  key with a different payload fails without mutation.
- Capture locks the closeout case/current pointer and profile version, then reads
  source heads under the strongest safe source contract. It records explicit
  before/after watermarks where cross-domain snapshot isolation cannot provide a
  single transaction-wide source snapshot.
- Review, accept, reject, reopen, assignment and correction lock and re-read the
  case, target assessment, current pointer and relevant source heads in a
  documented deterministic order inside `transaction.atomic()`.
- Permission, active Tenant/membership, object scope, lifecycle, SoD, source
  freshness and evidence access are rechecked inside the transaction.
- Concurrent capture cannot create two current completed assessments for the same
  case/profile/cutoff/idempotency identity. Concurrent acceptance/reopen produces
  one winner; the loser receives a safe stale-state conflict.
- Failed/cancelled attempts and source-read errors never replace the last valid
  current assessment. A crash cannot leave an accepted event without its audit
  and immutable item evidence.
- No source row is locked merely to create an implicit cross-domain mutation.
  If a stable source read cannot be proved, the item is `stale`, `unknown`,
  `incomplete` or `unverifiable` and acceptance fails according to the profile.

## 6. Permissions and separation of duties

Every proposed code requires a `BusinessPermissionCode`, registry entry,
expand-only catalogue/default-grant migration, view and service enforcement, and
Tenant/object-scope tests. **Recommended default grants: none.** Existing
Reporting, reconciliation, source, Owner/Admin, position, assignment or workflow
permissions imply none of these permissions.

| Proposed permission | Consequential boundary |
| --- | --- |
| `reporting.project_closeout_profile.view` | View published profile metadata only. |
| `reporting.project_closeout_profile.prepare` | Prepare a profile version; cannot publish. |
| `reporting.project_closeout_profile.publish` | Publish/supersede/retire after source-owner review; author cannot publish own version. |
| `reporting.project_closeout_case.view` | View minimized permitted case/assessment status. |
| `reporting.project_closeout_case.prepare` | Create/activate a Tenant/project-scoped case and run explicit synchronous assessment. |
| `reporting.project_closeout_case.coordinate` | Assign/record notes and source-action proposals; grants no source authority. |
| `reporting.project_closeout_case.review` | Record review or rejection; reviewer differs from preparer for material cases. |
| `reporting.project_closeout_case.accept` | Independently accept a completed current assessment under the profile. |
| `reporting.project_closeout_case.reopen` | Reopen accepted evidence with reason and qualifying change; separately granted. |
| `reporting.project_closeout_evidence.link` | Link an already authorized exact DMS version; grants no byte access. |
| `reporting.project_closeout_sensitive.view` | View permitted masked/sensitive closeout facts; source/DMS permissions still apply. |
| `reporting.project_closeout_export.create` | Create a bounded on-demand export manifest/response for permitted rows. |
| `reporting.project_closeout_export.download` | Download the actor-bound short-lived result after reauthorization. |
| `reporting.project_closeout_audit.view` | View minimized closeout-control history; no source payload authority. |

SoD rules are mandatory:

1. a profile-version author cannot publish that version;
2. the case preparer/assessment runner cannot accept the same material case;
3. the last disposer of a material blocker or residual-risk proposer cannot be
   the sole acceptor;
4. a sensitive/security/integrity blocker requires an independent acceptor and
   cannot be accepted as residual risk by the actor who created/disposed it;
5. source owners act only under source-domain permissions and lifecycles; and
6. assignment, position, project role, Tenant Owner/Admin, Platform Admin and
   Superuser never bypass permissions or SoD.

Platform staff have no implicit Tenant access. They require the existing
independently approved, purpose-, time- and scope-bound Tenant-access grant, plus
the same P10/source/DMS permissions and audit evidence.

## 7. Privacy, masking, exports, DMS and audit

- Every case, assessment, item, assignment, event and export is Tenant-scoped and
  project/object-scoped. Cross-Tenant comparison, benchmarking and Platform
  browsing are excluded.
- The P10 snapshot stores only the minimum normalized control fact needed to
  explain the outcome. Sensitive payroll/person, bank, commercial, HSE/QA,
  precise-location, party and document fields retain the strictest source
  classification and masking. Counts/status may be shown when detail is denied;
  denial cannot be presented as source absence or zero.
- DMS alone owns bytes, immutable versions, retention and protected download.
  P10 stores exact version public identity/hash, evidence role and sensitivity.
  Linking does not grant preview/download; each access rechecks Tenant, object,
  source and DMS permissions. P10 never copies files into a second store.
- Export is explicit, synchronous, POST-only, audited, row/object filtered and
  CSV-only in this tranche. It includes profile/assessment/cutoff/freshness,
  visible non-value states and source/evidence identities only to the viewer's
  permission. The private response is non-cacheable, actor-bound and short-lived;
  Reporting stores no export bytes. Retention requires a separately authorized
  DMS upload that creates a new immutable `DocumentVersion` and hash pin.
- Audit stores action/control evidence, not source payloads or document bytes. It
  covers denied attempts, profile publication, case/capture, assignment,
  proposal, evidence link, review, accept/reject/reopen, correction and export,
  including Tenant, membership/capacity, public IDs, before/new state, reason,
  source/DMS pins, correlation/idempotency keys and result hashes.

## 8. Correction, reversal and supersession

| Situation | Required behavior |
| --- | --- |
| Source fact was wrong | Correct/reverse/supersede through the source domain; link exact correction evidence; create a successor assessment. |
| Source fact changed legitimately after cutoff | Historical assessment stays true to its cutoff; mark current presentation stale and assess again if required. |
| P10 assessment logic/profile changes | Publish a new profile version; create a new assessment. Never reclassify accepted history in place. |
| P10 metadata/evidence link was wrong | Append correction/supersession evidence with actor, reason and before/after hashes; do not edit accepted evidence. |
| Acceptance was unsafe or later invalidated | Reopen through separate permission and reason, retaining the acceptance; use a successor assessment and new decision. |
| A domain action must be undone | Use that domain's authorized reversal/correction lifecycle. P10 records the resulting state only. |

There is no destructive delete of published profiles, completed assessments,
accepted/rejected/reopened evidence, source pins, exports manifests or audit
history through normal application services.

## 9. Persian RTL/Jalali UI contract

The S16 workbench is Persian-first, RTL, responsive and accessible. It must:

- show project, profile/version, cutoff/as-of time, Tenant timezone, current and
  historical assessment state, coverage, freshness/staleness and acceptance
  scope in Persian labels;
- display Gregorian canonical storage as Jalali dates using the shared
  `erp_jalali` contract, with unambiguous time and timezone; technical identifiers
  and canonical numbers remain LTR where appropriate;
- group controls by owning domain and show the authority, source version/status,
  outcome, responsible coordinator, evidence, last change and required next
  source action;
- distinguish `unknown`, `incomplete`, `stale`, `unverifiable`,
  `not_applicable`, `gated/unavailable`, masked and unauthorized from zero,
  satisfied and no-record-found through text/icon semantics, never color alone;
- keep amounts labelled with currency and quantities with unit, and distinguish
  budget, commitment, actual, paid, forecast and variance;
- use accessible tables as the authoritative presentation; charts, if any, have
  table parity and add no hidden aggregate;
- preserve URL filter/sort/page state, stable pagination, keyboard/focus/error
  behavior and private non-cacheable responses;
- show recorded-at-cutoff versus current-source state, immutable history,
  correction/supersession lineage and explicit downstream no-effect wording; and
- expose only actions the actor is authorized to know/use, with POST/CSRF,
  stale-state confirmation, consequence summary and safe concurrency errors.

## 10. Expand-only, non-fabricating migration posture

S14–S17 may add only accepted P10 closeout tables, constraints, indexes and
permission-catalogue rows. It may not rename/drop/retype a source field, backfill
or edit a source-domain status, create a new project completion field, promote
legacy `financials`, replace native reconciliation/evidence, or activate a
producer/consumer.

No migration may infer a profile, required item, source owner/version/status,
cutoff, applicability, completeness, disposition, freshness, acceptance,
residual-risk decision, evidence link or permission grant. Legacy zero/default,
absence and mutable labels are not evidence. Backfill is permitted only where
every authoritative input and deterministic rule already exist; otherwise the
new field remains nullable/unknown and consequential use fails closed.

Existing projects receive no fabricated closeout case or completed checklist.
Creation is an explicit authorized runtime action after profile publication.
Rollback removes only the new P10 structures/catalogue rows after proving no
source-domain or P10-S02–S13 record changed. Contract/removal work is not
authorized.

## 11. Downstream no-effect rules

No S14–S17 profile, case, assessment, item, coordination request, evidence link,
review, acceptance, rejection, reopen, correction or export may:

- change a project/site/WBS/CBS/schedule/budget/forecast or declare a project
  operationally, contractually, financially or legally closed;
- approve/close/amend/release a contract, instruction, variation, Claim/EOT,
  guarantee, insurance/clearance, retention or commercial exposure;
- certify/correct a claim/certificate, recognize/write off AP/AR, settle cash,
  post/reverse a journal or close/reopen an accounting period;
- reserve/release/transfer/count/post/value/dispose inventory;
- complete/correct maintenance, capitalize/depreciate/impair/transfer/dispose a
  fixed asset, or create Project Cost actuals;
- close/reopen an incident, inspection, permit, finding, NCR or CAPA;
- upload, publish, approve, archive, delete or change retention for a document;
- create, approve, sanitize, publish or supersede Knowledge;
- rerun/review/close a metric or reconciliation outside its S02–S13 service;
- complete a shared workflow work item, grant permission or create an implied
  source assignment; or
- notify a provider, call an integration, enqueue/schedule work, invoke AI/RAG/
  vector analytics, or activate production behavior.

## 12. Complete Product Owner decision register

Every material decision has a stable ID. **The Product Owner accepted Option A for
every decision on 2026-10-07.**

| ID | Realistic options | Recommendation and rationale | Session |
| --- | --- | --- | --- |
| `P10-C01` Envelope | A: S14–S17 only; B: include S18 certification; C: include S18–S24 | **A.** Matches the official map and preserves certification/production gates. | All |
| `P10-C02` Owning boundary | A: Reporting owns derived control/acceptance evidence only; B: Projects owns a new universal closeout engine; C: P10 owns source closure | **A.** Provides one governed view without displacing source authorities. | All |
| `P10-C03` Closeout meaning | A: profile-at-cutoff control acceptance only; B: automatic project closure; C: legal/financial certification | **A.** Keeps the assertion precise and prevents downstream implication. | All |
| `P10-C04` Profile governance | A: code-governed registered families with immutable versions; B: Tenant-authored executable rules; C: free-text checklist | **A.** Deterministic, bounded and non-executable. | S14–S17 |
| `P10-C05` Initial family set | A: the nine families in section 3.2; B: generic arbitrary sources; C: contracts/finance only | **A.** Covers roadmap scope while naming authority and gaps. | S14–S17 |
| `P10-C06` Project lifecycle | A: Projects remains authoritative and P10 has no status effect; B: P10 writes `closed`; C: mirror bidirectionally | **A.** Avoids dual state and accidental closure. | All |
| `P10-C07` Source access | A: registered read adapters plus source permission recheck; B: unrestricted ORM/SQL; C: copied totals | **A.** Preserves authorization, lineage and adapter ownership. | S14–S17 |
| `P10-C08` Missing/unknown data | A: explicit non-value statuses; B: zero/complete; C: omit | **A.** Non-fabricating and audit-visible. | S15–S17 |
| `P10-C09` Applicability | A: versioned rule plus evidence; B: preparer checkbox; C: missing means N/A | **A.** Prevents silent waiver. | S14–S17 |
| `P10-C10` Material open items | A: only profile-named residual risks with independent evidence; B: accept any open item; C: require no open item regardless of policy | **A.** Risk-proportionate without waiving security/authority/integrity. | S15–S17 |
| `P10-C11` Assessment execution | A: explicit bounded synchronous capture; B: automatic on source writes; C: scheduler/queue | **A.** Matches current infrastructure and gate. | S15–S17 |
| `P10-C12` Cutoff/freshness | A: canonical cutoff, watermarks and versioned freshness; B: page-time heads; C: generated date only | **A.** Enables reproducible evidence and stale detection. | S14–S17 |
| `P10-C13` Case lifecycle | A: lifecycle in section 4 with append-only events; B: editable complete flag; C: source-workflow state | **A.** Auditable without duplicating source workflows. | S14–S17 |
| `P10-C14` Accepted history | A: immutable assessment/acceptance plus successor; B: edit in place; C: delete/recreate | **A.** Preserves governed evidence. | S15–S17 |
| `P10-C15` Source corrections | A: source lifecycle then successor assessment; B: P10 corrects source; C: P10 overlay becomes truth | **A.** Retains domain ownership. | S15–S17 |
| `P10-C16` Reopen | A: separately permissioned append-only reopen with reason/change; B: overwrite acceptance; C: never reopen | **A.** Correctable and historically faithful. | S16–S17 |
| `P10-C17` Locking | A: deterministic locks/re-read inside atomic services; B: optimistic UI only; C: last writer wins | **A.** Prevents lost decisions and split audit evidence. | S14–S17 |
| `P10-C18` Idempotency | A: command-scoped keys and payload conflict rejection; B: best-effort duplicate check; C: none | **A.** Makes retries safe and exact. | S14–S17 |
| `P10-C19` Stale source during capture | A: explicit stale/incomplete result and fail closed; B: mix versions; C: retry invisibly until passing | **A.** Honest evidence with bounded execution. | S15–S17 |
| `P10-C20` Permission catalogue | A: 14 dedicated default-deny codes in section 6; B: reuse broad Reporting view/manage; C: Owner/Admin implicit | **A.** Least privilege for consequential acceptance/export. | S14–S17 |
| `P10-C21` Profile SoD | A: author cannot publish and source owners review family contracts; B: self-publish; C: universal platform publisher | **A.** Protects source semantics without granting Platform access. | S14–S17 |
| `P10-C22` Case acceptance SoD | A: independent acceptor for material case/blocker; B: preparer accepts; C: no recorded acceptor | **A.** Separates evidence preparation from acceptance. | S16–S17 |
| `P10-C23` Platform access | A: no implicit access; purpose/time/scope grant plus ordinary permissions; B: Platform Admin implicit; C: global support role | **A.** Preserves Tenant isolation and accepted support policy. | All |
| `P10-C24` Sensitive data | A: minimize/mask and require source plus dedicated sensitive permission; B: copy full payload; C: hide all evidence | **A.** Least disclosure with explainability. | S15–S17 |
| `P10-C25` DMS boundary | A: exact version/hash pins; DMS owns bytes; B: copy bytes to Reporting; C: mutable URLs | **A.** One evidence authority and retained integrity. | S15–S17 |
| `P10-C26` Export | A: bounded synchronous private CSV, byte-free manifest; B: scheduled/provider delivery; C: unrestricted workbook/archive | **A.** Useful audit handoff without new infrastructure or leakage. | S16–S17 |
| `P10-C27` Retained export | A: explicit DMS upload/new version; B: Reporting blob; C: public link | **A.** Keeps retention and download under DMS. | S16–S17 |
| `P10-C28` Workflow/assignment | A: coordination history only; existing workflow remains sole action queue; B: second work-item engine; C: assignment grants permission | **A.** Avoids duplicate workflow and privilege. | S14–S17 |
| `P10-C29` UI/localization | A: Persian RTL/Jalali with accessible tables and explicit non-values; B: English admin only; C: chart-only | **A.** Meets product UI rules and prevents false completion. | S16–S17 |
| `P10-C30` Migration | A: expand-only/non-fabricating; B: infer legacy completion; C: replace source closeout/history | **A.** Preserves compatibility, truth and rollback. | S14–S17 |
| `P10-C31` Existing projects | A: no automatic case/backfill; explicit authorized creation; B: create completed cases; C: infer from project status | **A.** Prevents fabricated history. | S14–S17 |
| `P10-C32` Downstream effects | A: none; B: automatically close project/contracts/periods; C: selectively trigger financial actions | **A.** Keeps S14–S17 a governed control only. | All |
| `P10-C33` Knowledge | A: pin reviewed publication/absence only; B: auto-create lesson; C: AI summary becomes evidence | **A.** Preserves Knowledge authority and AI gate. | S15–S17 |
| `P10-C34` Acceptance evidence | A: focused PostgreSQL/migration/no-effect assurance plus Product Owner acceptance; B: engineering self-accepts; C: production certification | **A.** Proportionate and preserves S18+. | S17 |
| `P10-C35` Runtime owner | A: Product Owner go/no-go; Authorized Technical Maintainer executes non-production release/rollback; B: implementer self-authorizes; C: unspecified | **A.** Separates product decision from technical execution. | S14–S17 |
| `P10-C36` Open unrelated debt | A: retain six permission-registry failures as separately tracked non-blocking debt; B: absorb/fix in S14–S17; C: treat as closeout failure | **A.** Keeps scope truthful without hiding known debt. | All |

**Recorded Product Owner decision:** `P10-C01`–`P10-C36 = Option A`; authorize
only the bounded S14–S17 runtime described here.

## 13. Focused PostgreSQL acceptance criteria

The implementation acceptance plan is intentionally bounded. It requires a real
PostgreSQL database and at least these focused cases:

1. **Catalogue/permissions:** exactly the accepted profile families and 14 new
   permission codes exist; all default roles have none; author self-publication
   and incomplete source-owner review fail.
2. **Tenant isolation:** cross-Tenant case, assessment, item, source/evidence pin,
   export and guessed-public-ID reads/writes return safe denial/non-disclosure;
   Platform Admin/Superuser has no implicit Tenant access.
3. **Object scope:** project/site/domain object restrictions are enforced at
   list, detail, capture, drill-through, evidence link, accept/reopen and export.
4. **Source authority:** each family pins the authoritative version/status and
   source permission; P10 cannot mutate any source model or call a consequential
   source transition.
5. **Non-fabrication:** absent, inaccessible, incomplete, stale, incompatible and
   gated inputs remain distinct and never produce zero, satisfied or N/A.
6. **Cutoff/reproducibility:** fixed source versions/watermarks reproduce the same
   manifest and fingerprint; a newer source produces stale/successor evidence
   without rewriting the prior assessment.
7. **Lifecycle/SoD:** invalid transitions, self-publish, material self-review/
   self-accept and last-disposer sole acceptance fail; accepted/rejected/reopened
   events and source pins are immutable.
8. **Concurrency/idempotency:** concurrent capture and accept/reopen yield one
   authoritative winner; identical retry returns it; conflicting payload/key and
   stale version fail without partial history.
9. **Atomicity:** injected failure rolls back case/current pointer, assessment,
   items, event and audit together; failed/cancelled work never replaces current.
10. **Correction/supersession:** source correction plus successor assessment
    preserves original acceptance; P10 metadata correction is append-only.
11. **DMS/privacy:** exact version/hash pinning, download reauthorization,
    masking and sensitive permission work; unavailable evidence is not absence;
    no bytes are stored in Reporting.
12. **Export:** CSV is explicit POST-only, permission/object filtered, private,
    actor-bound, audited and byte-free at rest; retained copy uses DMS only.
13. **RTL/Jalali/UI:** canonical dates persist unchanged while Jalali dates,
    Persian RTL labels, LTR identifiers, accessible tables and all non-value/
    concurrency/error states render correctly.
14. **Downstream no-effect:** before/after assertions prove zero project/contract/
    claim/AP-AR/Treasury/Accounting/Inventory/Equipment/Fixed Asset/HSE/QA/DMS/
    Knowledge/workflow mutation from every P10 command.
15. **Migration:** clean-schema apply, bounded rollback and reapply pass; migration
    does not fabricate cases/items/acceptance or change P10-S02–S13/source rows.
16. **Repository gates:** targeted tests, `manage.py check`, focused Ruff,
    template/URL checks, migration drift and documentation/stale-claim checks pass.

The known six unrelated permission-registry failures are reported separately and
must not be relabelled as S14–S17 failures or silently fixed under this authority.
Any newly introduced closeout permission failure is blocking.

## 14. Implementation validation and authoritative-document closeout

S17 closeout verified:

- `ROADMAP.md` and the execution playbook identify P10-S14–S17 as Product Owner
  accepted, with S18+ still gated;
- the accepted S01–S06 and S07–S13 packets remain historical authorities and are
  not rewritten;
- `DOMAIN_MODEL.md`, `DATA_MODEL.md`, `DOMAIN_AND_DATA_MODEL.md`,
  `PRODUCT_CAPABILITY_AND_READINESS_AUDIT.md`,
  `WORKFLOW_AND_PERMISSION_MATRIX.md`, `USER_CAPABILITY_MAP.md` and
  `docs/ui-guidelines.md` remain consistent with source ownership, DMS custody,
  privacy, workflow and UI rules; and
- no runtime-status document grants P10-S18+ or production authority from this
  acceptance.

The Product Owner accepted this validation evidence: 16 focused PostgreSQL cases
passed in 946.61 seconds in one runner against the uniquely named disposable
database `test_p10_s14_s17_accept_20261007_a91f`; `test_construction_erp` was not
used. Clean-schema apply and dependency-safe Reporting/Organizations rollback and
reapply passed, and the disposable database was removed afterward. Django system
check, migration drift, targeted Ruff, template/URL and `git diff --check` passed.
The accepted validation fixes cover nullable-join locking, retry fingerprint
ordering, exact DMS hash validation, cutoff precision, unsafe Knowledge UUID
association, enum naming and import ordering. The implementation creates no
automatic case/backfill and no source or downstream mutation. The six unrelated
permission-registry failures remain separately tracked non-blocking debt.

## 15. Preserved gates

The following remain explicitly gated:

- all `P10-S18+`, including release certification, independent production-risk
  review, UAT/release recommendation, final phase closeout, cutover and activation;
- AI, RAG, vector search/analytics, predictive/autonomous analytics and Tenant-
  authored executable query/formula behavior;
- providers, queues, schedulers, notifications, integrations, external BI/
  warehouse delivery and scheduled reports/exports;
- every automatic project, contract, claim, document, asset, stock, workflow,
  Knowledge, AP/AR, Treasury, Accounting, Project Cost, Payroll, regulatory or
  other downstream/financial effect;
- cross-Tenant analytics/benchmarking and implicit Platform Admin Tenant access;
  and
- production data migration, certification, deployment and use.

The six unrelated permission-registry failures remain separate non-blocking debt.
Their preservation is not approval to ignore newly introduced failures.

## 16. Exact bounded runtime-authorization wording

The Product Owner supplied the following exact authorization before implementation;
it is retained as the historical bounded-runtime record:

> I accept `P10-C01`–`P10-C36 = Option A` as recorded in
> `docs/architecture/P10_S14_S17_PROJECT_CLOSEOUT_COORDINATION_DECISION_PACKET.md`
> and authorize implementation of **P10-S14–S17 only**: the code-governed
> project-closeout profile; Tenant/project-scoped immutable assessment and
> coordination evidence over the nine named source-authority families; explicit
> synchronous capture; append-only review, acceptance, rejection, reopen and
> successor semantics; the 14 default-denied permissions; Persian RTL/Jalali
> workbench; exact DMS pins; and bounded private on-demand CSV export. Source
> domains remain authoritative and Reporting remains a derived/governed control
> only. Unknown or unavailable data must never become fabricated zero or
> completion; accepted historical evidence is immutable; Tenant isolation and no
> implicit Platform Admin Tenant access are mandatory. The Product Owner is the
> S17 acceptance/go-no-go owner and an Authorized Technical Maintainer may execute
> the bounded non-production release/rollback. This authorization excludes
> `P10-S18+`, AI/RAG/vector analytics, providers, queues/schedulers, integrations,
> all automatic downstream or financial effects, and production activation. The
> six unrelated permission-registry failures remain separate non-blocking debt.

Anything less specific remains planning approval only and does not authorize
runtime implementation.

## 17. Final Product Owner handoff

1. **Exact S14–S17 decomposition:** section 2 fixes S14 foundation, S15 explicit
   synchronous assessment, S16 governed review/acceptance/UI/export and S17
   focused PostgreSQL assurance/documentation closeout.
2. **Ownership/authority model:** section 3 fixes Reporting as derived control
   owner only and identifies the nine authoritative source families.
3. **Lifecycle and control semantics:** sections 4, 5 and 8 fix immutable
   profile/case/assessment evidence, explicit non-values, stale detection,
   concurrency and successor-only correction.
4. **Permissions/SoD:** section 6 records 14 accepted default-denied permissions, no
   implicit role access and independent publication/material acceptance.
5. **Complete decision register:** section 12 contains stable `P10-C01`–
   `P10-C36`, each with realistic alternatives, recommendation and rationale.
6. **Recorded option for each decision:** Option A for every `P10-C01`–
   `P10-C36`, accepted by the Product Owner on 2026-10-07.
7. **Validation plan:** section 13 defines 16 focused PostgreSQL, migration,
   tenant/permission, history, concurrency, UI/export and no-effect criteria.
8. **Preserved gates:** section 15 keeps P10-S18+, AI/RAG/vector analytics,
   providers, queues/schedulers, integrations, downstream/financial effects and
   production activation gated; the six unrelated permission-registry failures
   remain separate non-blocking debt.
9. **Acceptance boundary:** P10-S14–S17 is Product Owner accepted; this acceptance
   grants no P10-S18+ or production authority.
