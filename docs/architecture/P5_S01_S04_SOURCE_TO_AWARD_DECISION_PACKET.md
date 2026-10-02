# P5-S01–S04 Internal Source-to-Award Decision Packet

**Prepared:** 2026-10-01
**Status:** P5-S01–S04 planning and design complete; P5-D01–P5-D08 Option A were
accepted with clarification on 2026-10-02. P5-S05 and the separately authorized
P5-S06 sealed internal quote-capture tranche, P5-S07 bounded close-custody tranche and
P5-S08 pre-production sealed commercial-content custody tranche were implemented and
accepted on 2026-10-02. P5-S09 was subsequently authorized, its consolidated
decisions accepted, and its bounded protected-opening runtime accepted on 2026-10-02.
P5-S10 is subsequently authorized, implemented, PostgreSQL-verified and Product
Owner accepted under the separately accepted
[P5-S10 decisions](P5_S10_PRODUCT_OWNER_DECISIONS.md). P5-S11 is subsequently
implemented, PostgreSQL-verified and Product Owner accepted under its
[P5-S11 decision packet](P5_S11_PRODUCT_OWNER_DECISION_PACKET.md); its scoped
award self-finalization supersession of P5-D01 is recorded in section 8.

**Authority:** The Product Owner authorized P5-S01–S04 as one documentation-only
planning-and-design tranche on 2026-10-01. This packet is the authoritative result.
It creates no runtime feature, model, migration, permission, portal access,
financial posting, inventory receipt, supplier invoice, producer registration or
production activation. P5.2 remains deferred.

## 1. Four-session disposition and boundary

| Session | Completed design outcome | Acceptance evidence |
| --- | --- | --- |
| P5-S01 | Defined internal RFQ-to-award ownership, lifecycles, immutable evidence, source-of-truth boundaries and legacy containment. | Sections 3–5. |
| P5-S02 | Defined requester/buyer/evaluator/award/receiver separation, object scope, confidentiality, audit, withdrawal and correction rules. | Section 6 and P5-D01–P5-D04. |
| P5-S03 | Defined dormant future contracts to Project Cost, AP/GL, Treasury and Inventory. | Section 7 and P5-D05–P5-D08. |
| P5-S04 | Prepared the Product Owner decisions and the bounded, conditional P5-S05 implementation contract. | Sections 8–11. |
| P5-S06 | Added sealed internal quote-envelope and immutable revision metadata only, with no commercial-content persistence or reveal path. | P5-S06 acceptance in section 11. |
| P5-S07 | Added immutable synchronous metadata-only deadline-close custody. | P5-S07 acceptance in section 11. |
| P5-S08 | Added bounded pre-production immutable custody of permitted sealed supplier package bytes. | Section 12 and P5-S08 acceptance. |

| Boundary | Contract |
| --- | --- |
| Included | Internal sourcing design from an approved need through RFQ, invitation, quote revision, comparison and award; authorization/privacy policy choices; immutable evidence; legacy compatibility; future downstream handoff envelopes; a conditional P5-S05 contract. |
| Excluded | Code/schema/migrations, permission-catalog writes, data migration/backfill, UI, portal/external identity, supplier invoice/match, PO change, service acceptance, financial or stock producer, journal/open item/payment proposal/stock movement, pilot/cutover and production activation. |
| Direct evidence | Current Procurement models/services/tests; existing Parties, Workflow, DMS, Project Cost, AP/AR, Accounting, Treasury and Inventory boundaries; the P4-S38 handoff and active domain/data/permission architecture. |
| Stop condition | This packet, Roadmap and playbook are reconciled and validated. P5-D01–P5-D08 are accepted. No runtime work follows without a separate explicit P5-S05 implementation authorization. |

## 2. Verified current baseline

1. Procurement currently owns tenant/project-scoped `PurchaseRequest`,
   `PurchaseOrder` and `GoodsReceipt` aggregates with Decimal quantities/prices,
   service authorization, row locking, audit and finalized-record guards.
2. Purchase requests use `draft -> submitted -> approved/rejected/cancelled` and
   the shared workflow runtime. Purchase orders use
   `draft -> issued -> completed/cancelled`. Goods receipts use
   `draft -> posted -> void`; void can reopen a completed order.
3. A current PO may be created directly against an approved request and supplier
   `BusinessParty`. There is no RFQ, invitation, quote, comparison, sourcing
   decision, award version, PO-change version, supplier invoice or match model.
4. A posted goods receipt is Procurement operational evidence. Tests explicitly
   establish that it does not automatically create Inventory. A separately
   permissioned Inventory command can reference a posted receipt line, and a
   posted stock movement must be reversed before that receipt can be voided.
5. Parties owns the tenant-local supplier identity and role. Procurement must not
   create another supplier master. DMS owns private immutable file versions;
   sourcing records own business meaning and may link version-pinned evidence.
6. Project Cost contains inert, registered source contracts and immutable facts
   with source version/line/occurrence, coding, reversal and incomplete-coverage
   evidence. No Procurement producer is registered.
7. AP/AR provides immutable source-resolved obligations and reconciliation, but
   no supplier-invoice source adapter or posting activation exists. Accounting is
   the sole journal authority; Treasury is the sole cash/payment authority.
8. Existing permissions cover requests, orders and receipts. They do not grant
   RFQ, confidential-quote, evaluation, award or override authority.

## 3. Target ownership and source-of-truth boundaries

| Fact | Authoritative owner | Boundary |
| --- | --- | --- |
| Supplier identity, tenant-local role and future qualification/restriction/onboarding status | Parties | `BusinessParty` is the sole tenant-local supplier identity. Identity, role, qualification, restriction, onboarding and permission to participate remain distinct; Procurement may snapshot eligibility evidence but cannot own or silently alter it. |
| Approved need and requested quantity | Procurement purchase request/version | RFQ lines snapshot and trace the selected request lines; an RFQ never rewrites the approved request. |
| RFQ terms, invited parties and clarification/addendum history | Procurement sourcing | Issued versions are immutable; a later addendum/version supersedes rather than edits them. |
| Supplier offer and each revision | Procurement sourcing | Every received revision retains source channel, captured-by actor, supplier attribution, received time, original document versions and integrity fingerprint. |
| Normalization and evaluation | Procurement sourcing | Derived comparison values never overwrite supplier assertions; method, exchange/precision policy, exclusions and evaluator evidence are pinned. |
| Award decision | Procurement sourcing | An approved immutable award identifies the governing RFQ, quote revisions, comparison version, selected lines, approvers, reasons and exceptions. It is not yet a PO, commitment posting, liability or payment authority. |
| Commercial commitment | Issued PO version in Procurement | A future PO/change explicitly consumes an award; an award alone must not create Project Cost or Accounting facts. |
| Receipt or service acceptance | Procurement operational acceptance | It is distinct from Inventory quantity and supplier-invoice liability. |
| Supplier invoice and liability | AP/Finance | AP/Finance owns supplier-invoice versions/lines and payable disposition. The matching service consumes Procurement and AP/Finance sources and owns only immutable derived match evidence; Accounting alone owns the journal. |
| Stock quantity/value | Inventory | Procurement may request a handoff; only Inventory finalizes/reverses its ledger fact. |
| Cash/payment | Treasury | Procurement and AP may supply eligibility/reference evidence; only Treasury proposes/releases/clears cash. |

All records, queries, relationships, uniqueness, commands and audit evidence are
organization-scoped. Project/site scope can only restrict access. Active
membership, active Tenant, business permission, object scope, current assignment
where used, and effective SoD policy are rechecked in the locked transaction.

## 4. Internal RFQ-to-award lifecycle

The lifecycle below is a design contract, not implemented state.

| Aggregate | Target lifecycle | Immutable/fail-closed rule |
| --- | --- | --- |
| RFQ | `draft -> submitted_for_issue -> issued/open -> closed -> under_evaluation -> awarded/no_award`; `returned` from issue review; reasoned `cancelled` before award | Issue freezes a numbered RFQ version, terms, lines, requested delivery and invited-party set. Material correction after issue creates an addendum/new version and auditable supplier notification; it never edits the issued version. |
| Invitation | `prepared -> sent -> acknowledged/declined/expired/withdrawn/closed` | Identity, RFQ version, recipient, channel, send/expiry facts and delivery evidence are retained. Withdrawal closes only that invitation and cannot erase a quote already received. |
| Quote | Stable supplier/RFQ envelope containing append-only revisions | A revision moves through `captured -> submitted -> withdrawn/superseded` and, under the selected privacy policy, `opened -> admissible/nonconforming -> evaluated`. Submitted price/term lines are immutable. |
| Comparison | `draft -> finalized -> superseded` | Pins eligible quote revisions, normalized values, declared assumptions, exclusions, scoring method/version, evaluator entries and generated time. Recalculation creates a version. |
| Award proposal/decision | `draft -> submitted -> approved/rejected/withdrawn`; approved decision may later be `superseded` or `rescinded` by linked decision | Approval pins line-level supplier selection, quantities, governing quote/comparison versions, reasons, exceptions and approval evidence. Correction never rewinds or deletes an approved award. |

Rules common to the lifecycle:

- one RFQ version has a single close/opening policy and timezone-aware deadline;
  the earliest opening time derives from the effective issued version and approved
  addenda, and manual closure never permits early opening;
- a supplier may withdraw or supersede before closing; every submitted revision
  remains immutable and retained, and closing freezes the exact latest active
  revision that is valid against the effective RFQ/addenda at the authoritative
  closing time;
- late, incomplete, alternate or nonconforming bids are retained and explicitly
  classified, never silently dropped or normalized into compliance. Late bids are
  ineligible by default with no Buyer override; any exception requires a separately
  approved explicit and audited policy;
- evaluation uses the supplier's frozen assertions plus separately identified
  normalization; derived totals and scores are reproducible Decimal calculations;
- whole-RFQ, line, lot, partial-quantity, alternate and split awards are allowed
  only when the effective RFQ/addenda defined that structure in advance and gave
  suppliers a fair opportunity to price it. Award conserves quantity across the
  approved need, RFQ line, supplier offer, award and future PO consumption, with
  every unawarded remainder explicit;
- `no_award`, cancellation, rescission, exceptional acceptance and every override
  require a reason, actor/time, authority and immutable audit evidence;
- workflow coordinates registered domain commands; it cannot generically mutate
  sourcing state or use signals to synchronize an award.

## 5. Evidence, correction and legacy compatibility

The minimum immutable evidence set is Tenant, public identity, project/request and
line lineage, RFQ and addendum versions, invited supplier identity, quote/revision
and original document-version identities, capture channel/actor/time, deadline and
late flag, currency/precision snapshot, terms/tax/freight/delivery assertions,
comparison method/version and inputs, conflicts/abstentions, transitions,
decisions/reasons, override authority, and audit correlation/idempotency identity.

Corrections are append-only:

- before issue/submission, a draft may be edited by its authorized maker;
- after issue, RFQ correction is a new addendum/effective version with impact
  classification and supplier notification evidence; material change equitably
  extends or reopens the competition for every affected invitee;
- after quote submission, correction is a supplier-attributed revision or a
  buyer-captured revision backed by supplier evidence, never an in-place edit;
- after closing, ordinary commercial revision or renegotiation is prohibited.
  Clarification may resolve genuine ambiguity or obtain confirmation/evidence but
  cannot materially change price, quantity, scope, delivery commitment, commercial
  qualification, payment terms or risk allocation. Such a material correction is
  barred unless a separately approved exception process explicitly permits it;
- after award approval, correction is rescission/supersession plus a new decision;
  any later PO correction belongs to PO-change authority, not award mutation.

Existing requests, POs and receipts remain valid with their current identifiers,
states and audit history. They are classified as `legacy_direct` when sourcing
lineage is absent; no RFQ, quote, award or version history is fabricated. New
optional links are expand-only and must not make old rows unreadable or block
current receipt behavior. A future cutover requires inventory, mapping, dependency,
reconciliation, rollback and retention evidence before any legacy field removal.

## 6. Authorization, SoD, confidentiality and object scope

The target responsibilities are distinct capabilities, not job titles:

| Responsibility | May do | Must not imply |
| --- | --- | --- |
| Requester | create/submit need; answer need clarification | invite suppliers, reveal bids, evaluate, approve award or receive by virtue of authorship |
| Buyer | draft/issue RFQ, manage invitations/addenda and capture attributable correspondence | score alone, approve own award, alter submitted supplier assertions or receive by virtue of buyer access |
| Confidential-bid custodian/opening officer | see restricted metadata; perform controlled reveal/open | evaluate or award merely because bid content is visible |
| Evaluator | view opened eligible bids in assigned scope; record scoring/conflict/abstention | alter bids, invite, approve own recommendation or see unrelated RFQs |
| Award approver | approve/reject submitted award within threshold and scope | bypass eligibility, missing evidence, conflicts or required independent approval |
| Receiver/service accepter | record physical receipt or service acceptance against issued PO scope | select supplier, create liability, post stock or release payment |
| AP/Accounting/Inventory/Treasury actor | act only through the future consuming-domain contract | gain sourcing authority from downstream permission |

Every capability requires dedicated `BusinessPermissionCode` entries, registry and
default-grant migrations, service and view enforcement, and positive/negative
tenant/object tests when implementation is authorized. Target families are RFQ
view/create/change/submit/issue/addendum/cancel, invitation manage, quote metadata/
capture/withdraw/open/view-confidential, comparison prepare/finalize, award
propose/approve/rescind and sourcing override. Each slice registers only its own
capabilities. Conditional P5-S05 is limited to the RFQ and invitation permissions;
their default grants must implement P5-D01/P5-D02 rather than pre-empt them.

Confidentiality defaults fail closed. Under accepted P5-D02, quote receipt/
administration and content visibility are separate capabilities. Before authorized
opening, no human actor may access prices, terms, attachments, qualifications or
other commercial content absent a future separately approved exception policy.
Only non-content receipt metadata, integrity results, quarantine state and safe
processing status may be visible. DMS previews/downloads, exports, search/indexing,
notifications, logs, errors, caches, generated documents and APIs enforce the same
boundary. Support impersonation, Owner/Admin status, position, workflow candidacy
and UI visibility never bypass it; emergency access remains governed by P5-D01.

Opening is immutable and revision-specific. It reveals only revisions that are
explicitly opened and eligible; opening one revision does not expose withdrawn,
superseded, late, quarantined or other retained revisions. Only an opened eligible
revision may enter comparison, evaluation or award processing. Future downstream
contracts receive approved award/downstream identities, not competing confidential
quote content, unless a separately approved contract explicitly requires it.

The audit trail records successful and denied reveal/download/export, capture,
withdrawal, opening, admissibility, evaluation, conflict/abstention, comparison,
award, override, rescission and correction actions without leaking confidential
values into general logs. Under accepted P5-D01, break-glass access is time-bound,
reasoned, independently approved, narrowly scoped, read-only, prominently flagged
and fully audited. It cannot modify bids/evaluations, approve awards or exercise
other commercial decision authority. Owner/Admin status provides no bypass, and a
protected operation remains pending when its required independent actor is absent.

## 7. Dormant future handoff contracts

These envelopes constrain future design. None is registered, called or activated
by P5-S01–S04 or the proposed P5-S05.

| Consumer/owner | Eligible future source | Required identity and payload | Idempotency, correction and reconciliation | Fail-closed conditions |
| --- | --- | --- | --- | --- |
| Project Cost | Issued PO/change version for commitment; accepted receipt/service version for accrual when approved policy requires; AP/Accounting source for actual, never award alone | Tenant; source kind/UUID/version; stable line and occurrence; supplier/project/WBS/Activity/leaf CBS/cost center; quantity/UOM; IRR amount and precision-policy version; effective date; contract/status snapshot | Unique source contract + occurrence; exact retry returns existing fact, payload conflict rejects; reversal/replacement references original; explicit coverage status, watermark, excluded/unclassified facts and source-to-fact tie-out | Missing registered/approved source contract, governing version, coding, policy, currency/precision, permission, source finality or reconciliation identity |
| AP and GL | AP/Finance-owned approved supplier-invoice version/line plus governing match evidence creates an AP payable through a registered resolver; the AP/Accounting adapter alone creates a journal | Tenant; supplier; invoice UUID/version/line; PO/change and receipt/acceptance line coverage; tax/terms/due-date/currency snapshots; match result/exceptions/approvals; source hash; accounting rule/mapping/period/dimensions | AP source/idempotency uniqueness; exact duplicate returns existing obligation; correction uses debit/credit adjustment, reversal/replacement and linked Accounting reversal, never edits posted history; AP-to-source and AP-to-GL tie-out | Missing supplier identity, duplicate invoice policy result, match/tolerance authority, approval/SoD, open period, mapping/rule, precision, coding, evidence, or unresolved blocking discrepancy |
| Inventory | Posted Procurement goods-receipt version/line accepted for stock under a registered Inventory command; service acceptance never creates stock | Tenant; receipt UUID/version/line/occurrence; PO line; warehouse; material/UOM and pinned conversion/rounding policy; quantity; custody/date; lot/serial when required | Inventory-owned unique source occurrence; exact retry is stable; conflicting retry rejects; Procurement void requires prior Inventory reversal; receipt-to-stock quantity and exception reconciliation | Missing warehouse/material/UOM/custody, incompatible or already-reversed source, required tracking, permission, object scope or registered contract; never infer stock from Procurement status alone |
| Treasury | Approved AP payable may become a payment proposal/reference; Procurement never directly releases cash | Tenant; AP obligation/version/open balance; supplier and verified beneficiary reference; due date/terms; IRR amount/precision; proposed allocation; approval/correlation identity | Treasury owns proposal/release/settlement idempotency and correction; cancellation/reversal links to AP allocation and cash/journal reversal; AP-to-Treasury and cash-to-GL reconciliation | Missing AP authority/open balance, beneficiary verification, approval/SoD, account/mapping/period, currency/precision, duplicate protection or reconciliation identity |

Cross-cutting contract rules:

- a normal handoff has exactly one authoritative source owner, one consuming
  owner, one semantic event and one resulting fact family. A derived/composite
  calculation may consume immutable references from multiple authoritative
  domains, but owns only its derived result and cannot mutate source evidence or
  become a generic integration mechanism;
- only IRR is currently active; no adapter may infer Toman or FX. Monetary values
  use Decimal and a pinned effective precision/rounding policy; quantities retain
  explicit UOM and conversion evidence;
- a producer is code-registered, synchronous and transactional until a separately
  approved durable-delivery design exists. No signal, generic workflow action or
  UI callback may create downstream authority;
- award, PO, receipt, invoice, AP obligation, journal, stock movement, Treasury
  movement and Project Cost fact are distinct records. Links reconcile them;
- partial coverage is explicit. Missing facts are unknown, never zero or complete;
- downstream rejection leaves the source in a recoverable, visible pending/error
  state and records no false success. Retry uses the same occurrence identity;
- each owner controls its reversal. Cross-domain correction executes the approved
  ordered reversal contract atomically where possible and otherwise remains
  blocked/pending with visible reconciliation evidence; it never rewinds history.

## 8. Product Owner decision packet

P5-D01–P5-D08 are accepted as recorded below. Their acceptance defines the
prospective P5-S05 contract but is not implementation authority.

### P5-D01 — Sourcing SoD and emergency access

| Option | Consequence |
| --- | --- |
| **A — Protected reveal and award with independent actors; controlled read-only break-glass (ACCEPTED WITH CLARIFICATION)** | Requester/buyer/evaluator/award/receiver capabilities remain distinct. Confidential reveal and award approval are Protected Operations and never self-approved, except for the later explicitly scoped P5-S11 sourcing-only award finalization supersession recorded below. An emergency actor may receive independently approved, time-bound, narrowly scoped, read-only access, but cannot modify bids/evaluations, approve awards or exercise commercial decision authority. |
| B — Policy-configurable sourcing self-approval | Fits very small Tenants but materially raises collusion/conflict risk and requires threshold/scope policy plus conspicuous exception evidence. |
| C — Owner/Admin bypass | Rejected: role is not authority and bypass defeats deny-by-default control. |

**Decision:** **P5-D01 = A — ACCEPTED WITH CLARIFICATION (2026-10-02).**
Separation is primarily capability/permission separation and does not require five
different people. Distinct-user enforcement is mandatory for Protected sourcing
operations, especially confidential bid reveal and award approval; neither may be
self-approved, subject only to the later narrowly scoped P5-S11 sourcing-only award
supersession recorded below. Break-glass access must be independently approved, time-bound,
narrowly scoped, read-only and fully audited, and it grants no bid/evaluation
modification, award approval or other commercial decision authority. Tenant
Owner/Admin status provides no bypass. If an independent actor is unavailable,
the Protected operation remains pending rather than weakening the control.

**Later scoped supersession — P5-S11 sourcing-only award (2026-10-02):** The
Product Owner explicitly supersedes P5-D01's no-self-approval rule only for the
P5-S11 immutable sourcing-only award business operation. Award preparation and
finalization remain separate permissions and self-finalization is disabled by
default. An explicit Tenant business-operation self-approval policy may allow the
same authorized user to prepare and finalize that award, including for a small or
single-user Tenant. The applied policy version, actor, exact Tenant/object/revision
scope, decision and evidence must be retained in audit history. Without that active
policy, the authorized preparer and finalizer must differ.

This scoped exception never permits conflict self-clearance: an actor with an
unresolved conflict cannot prepare or finalize the affected award. It does not
extend to confidential reveal, break-glass, system/security/access operations, any
other Protected operation, or downstream PO, contract, AP, GL, Treasury/cash,
budget, access-grant or cross-domain action. It does not create automatic downstream
execution; downstream handoff remains separately authorized. Apart from this precise
P5-S11 sourcing-only award exception, P5-D01 remains fully controlling.

### P5-D02 — Quote visibility and bid privacy

| Option | Consequence |
| --- | --- |
| **A — Sealed until effective deadline/authorized opening (ACCEPTED WITH CLARIFICATION)** | Receipt administration exposes only non-content metadata. No human actor sees commercial content before the earliest opening time derived from the effective issued RFQ version and approved addenda. Protected opening is immutable, revision-specific and reveals only explicitly opened eligible revisions to authorized actors. |
| B — Buyer-visible on receipt, evaluator-visible after close | Easier operations but permits early information asymmetry and requires stronger monitoring. |
| C — Open internal visibility | Rejected for competitive sourcing because it cannot protect bid confidentiality. |

**Decision:** **P5-D02 = A — ACCEPTED WITH CLARIFICATION (2026-10-02).** Quote
receipt/administration and content visibility are separate capabilities. Before
authorized opening, no human actor—including Buyer, Owner/Admin, support,
requester, receiver or evaluator—may inspect commercial content absent a future
approved exception policy. Manual closure never advances the opening time.
Technical failures use non-content metadata, integrity checks, quarantine and a
controlled exception workflow, not ordinary human inspection. Confidentiality
applies across every rendering, transfer, index, notification, log, cache,
generated document and API path. Opening is immutable and revision-specific; only
explicitly opened eligible revisions may enter comparison, evaluation or award.
Owner/Admin and support receive no bypass, emergency access remains governed by
P5-D01, and downstream integrations receive no competing confidential quote
content without a separately approved contract.

### P5-D03 — Invitation, withdrawal, revision and correction

| Option | Consequence |
| --- | --- |
| **A — Equal-treatment controlled window (ACCEPTED WITH CLARIFICATION)** | Before closing, suppliers may withdraw or supersede while immutable history is retained; closing freezes one explicit eligible revision per supplier. Material RFQ changes create an effective addendum/version and equitable notice/deadline treatment. Late bids are ineligible by default. Post-close clarification may resolve ambiguity but cannot become material correction or renegotiation without a separately approved exception policy. |
| B — Buyer-approved post-close revisions | More flexible but increases favoritism risk and demands exceptional approval/evidence. |
| C — No revisions after first submission | Simple but discourages legitimate correction before deadline and weakens evidence quality. |

**Decision:** **P5-D03 = A — ACCEPTED WITH CLARIFICATION (2026-10-02).** RFQ
issue, addendum, deadline extension, invitation withdrawal, quote withdrawal,
clarification and exception approval are separate capabilities. Before closing, a
supplier may withdraw or supersede; all revisions remain immutable, while only the
latest active revision valid against the effective RFQ/addenda at the authoritative
closing time is eligible. Closing freezes its explicit revision ID, never an
ambiguous latest record. Material RFQ changes create a new effective version with
equitable notice and extension/reopening for affected invitees. Late submissions
remain evidence but are ineligible by default, with no Buyer override.

After closing, ordinary commercial revision or renegotiation is prohibited.
Clarification may resolve genuine ambiguity or obtain confirmation/evidence without
materially changing the offer. A change to price, quantity, scope, delivery,
commercial qualification, payment terms or risk allocation is a material
correction and is barred absent a separately approved exception process.
Clarification must not expose competitor identity/content, rankings, evaluation
position or target prices; materially shared ambiguity receives a consistent and
equitable approach unless justified otherwise. Every action retains immutable
actor/time/reason, predecessor/source, effective-version and audit evidence. Award,
PO and downstream handoffs pin the RFQ version, addenda, invitation, eligible quote
revision, clarification evidence and approved exception identities.

### P5-D04 — Award structure and exception authority

| Option | Consequence |
| --- | --- |
| **A — Controlled line-level, partial and split awards (ACCEPTED WITH CLARIFICATION)** | The effective RFQ/addenda defines permitted award structures in advance. Only eligible, materially conforming revisions may ordinarily be awarded. Award conserves quantities and uses a finalized comparison; non-lowest selection needs criterion-based independent approval, while material nonconformance cannot use an ordinary exception. Approved awards are immutable and corrected by rescission/supersession. |
| B — Whole-RFQ single-supplier award only | Simpler first release but does not fit common construction sourcing. |
| C — Buyer finalizes award directly | Rejected because recommendation and approval collapse. |

**Decision:** **P5-D04 = A — ACCEPTED WITH CLARIFICATION (2026-10-02).** The
effective RFQ/addenda must define in advance whether whole-RFQ, line, lot,
partial-quantity, alternate or split awards are permitted; approval cannot
introduce a structure suppliers lacked a fair opportunity to price. Only eligible
and materially conforming quote revisions may ordinarily be awarded. A non-lowest
selection requires criterion-based justification and independent approval;
material nonconformance cannot be waived through an ordinary award exception.

The comparison preserves original supplier assertions and separately calculates
the governing normalized/awardable commercial basis. Quantity conservation is
mandatory across approved need, RFQ line, supplier offer, award and future PO
consumption. Awarded quantity cannot exceed the applicable approved or offered
quantity absent a separately approved policy. Award proposal, award approval and
exception approval are distinct capabilities. No award becomes effective while
required conflicts, abstentions, quantity discrepancies, exceptions or approvals
remain unresolved. An approved award is immutable; correction uses rescission or
supersession. Award remains sourcing evidence only and creates no PO, Project Cost,
AP/GL, Inventory, Treasury or cash effect. Future PO creation must explicitly
consume approved award lines and retain exact award-to-PO quantity lineage.

### P5-D05 — Future match tolerance and discrepancy ownership

| Option | Consequence |
| --- | --- |
| **A — Versioned policy with domain-owned evidence and AP-controlled disposition (ACCEPTED WITH OWNERSHIP CORRECTION)** | Procurement owns PO/change and goods-receipt/service-acceptance evidence; AP/Finance owns supplier-invoice evidence and payable disposition; Inventory owns stock facts; Accounting/tax owners govern monetary/tax/precision/posting policy. Matching consumes these sources and owns only immutable derived evidence. Tolerance classifies/routes but never rewrites facts. |
| B — AP owns all tolerances and corrections | Centralized but allows AP to rewrite operational evidence it does not own. |
| C — Hard-coded global tolerance | Rejected: no Tenant/version/scope or effective-date control. |

**Decision:** **P5-D05 = A — ACCEPTED WITH OWNERSHIP CORRECTION AND
CLARIFICATION (2026-10-02).** Procurement owns PO/change and goods-receipt/
service-acceptance evidence. AP/Finance owns supplier-invoice evidence and payable
disposition. Inventory owns stock-ledger facts and reversal/replacement. Accounting/
tax owners govern monetary, tax, precision, rounding and posting policy. The
matching service consumes these authoritative sources and produces immutable,
versioned match evidence; it owns no source document. Each domain corrects only
its own facts through its approved lifecycle.

Tolerance only classifies and routes discrepancies. Quantity, price, measurement/
rounding, tax, freight/charges, duplicate and cumulative-coverage controls remain
distinct. Policies are Tenant-scoped, versioned, effective-dated and platform-
bounded. Missing policy, precision, UOM conversion, source version or coding fails
closed. Line and cumulative coverage both apply so splitting cannot bypass limits.
Only IRR is active; no Toman or FX behavior is inferred. Within-tolerance status
creates no AP release, GL posting, Treasury authority, stock or Project Cost fact.

A blocking discrepancy requires authoritative-source correction or a separately
requested and independently approved exception. Owner/Admin has no bypass and no
generic force-match exists. Exceptions never rewrite facts; material errors use
the owning domain's reversal/replacement lifecycle. Once an AP obligation or
journal depends on a match, replacement follows the defined downstream reversal
sequence first. Incomplete evidence stays explicitly incomplete, never zero,
complete or matched. Recalculation creates a new immutable match version and never
overwrites a result used by downstream financial evidence. Exact thresholds remain
deliberately undecided implementation/policy inputs.

### P5-D06 — Supplier identity, onboarding, support and portal boundary

| Option | Consequence |
| --- | --- |
| **A — Internal sourcing using tenant-local `BusinessParty` (ACCEPTED WITH CLARIFICATION)** | `BusinessParty` remains the sole authoritative tenant-local supplier identity. Parties owns identity, role, qualification, restriction and onboarding evidence; Procurement consumes/snapshots eligibility and internally captures attributable quotes without creating a supplier master or external principal. Platform support is technical only. P5-S05 creates internal invitation records only; P5.2 remains separately gated. |
| B — Couple internal sourcing to portal identity now | Blocks P5.1 on unresolved external identity/support and expands security scope. |
| C — Create a Procurement supplier master | Rejected duplicate authority. |

**Decision:** **P5-D06 = A — ACCEPTED WITH CLARIFICATION (2026-10-02).**
`BusinessParty` is the sole authoritative tenant-local supplier identity;
Procurement cannot create a parallel supplier master. Supplier identity, Supplier
role, qualification, restriction, onboarding and permission to participate are
distinct. A role alone implies neither qualification, unrestricted/approved RFQ
participation nor downstream financial authority. Required qualification or
restriction checks come from explicit versioned policy and fail closed when
evidence is missing. Procurement may consume and snapshot eligibility evidence but
does not own Party identity, qualification, restriction or onboarding state.

Internal quote capture separately identifies the represented supplier, original
channel/evidence and capturing employee. Later Party correction or merge never
rewrites historical sourcing/downstream identity. P5.1 supplier contacts remain
data, not authenticated principals, Tenant members or portal users. A future P5.2
external principal requires an explicit tenant-scoped `BusinessParty` relationship
and invite-scoped least-privilege capabilities, not ordinary Tenant membership.
Identity/onboarding implies no beneficiary-bank verification, AP approval, Treasury
authority, qualification approval or permission to transact. Platform support is
technical only and cannot bypass P5-D01/P5-D02 or exercise commercial authority.
P5-S05 remains limited to internal invitation records: no external delivery,
credentials, supplier authentication, outbound provider or other P5.2 function.

### P5-D07 — Future source-to-cost/AP/Inventory/Treasury ownership

| Option | Consequence |
| --- | --- |
| **A — Owner-controlled, registered handoff contracts (ACCEPTED WITH ARCHITECTURAL CORRECTION)** | A normal handoff has one source owner, consumer, event and result family. Registered adapters invoke the consumer with immutable source identities; consumers validate, persist, correct and reconcile their facts. Multi-source derived calculations own only immutable derived results and have no source mutation authority. |
| B — Procurement writes consumer tables | Rejected cross-domain authority and correction risk. |
| C — Signals/eventual best effort without durable delivery authority | Rejected false-success and recovery risk. |

**Decision:** **P5-D07 = A — ACCEPTED WITH ARCHITECTURAL CORRECTION AND
CLARIFICATION (2026-10-02).** A normal handoff contract has exactly one
authoritative source owner, one consuming owner, one semantic event and one
resulting fact family. A derived/composite calculation may consume immutable
references from multiple authoritative domains but owns only its derived result.
Supplier-invoice matching therefore consumes Procurement-owned PO/receipt/service-
acceptance evidence and AP/Finance-owned invoice evidence and produces only
immutable versioned match evidence. It is not a generic integration mechanism and
has no source-domain mutation authority.

Sources finalize only their evidence; consumers independently validate and own
resulting facts, correction, reversal and reconciliation. Adapters/workflow own
neither side. No generic signal, model save, workflow transition, UI callback or
background side effect creates downstream financial, cost, Inventory or Treasury
facts. Contracts pin source UUID/version/line/event/occurrence—never `current` or
`latest`. Exact retry is idempotent; conflicting retry fails closed. Consumers
revalidate Tenant, authorization, scope, source state, SoD, coding, policy,
precision, UOM, period, mappings and duplicates. Missing values are not inferred;
only IRR is active.

Corrections use owner-controlled reversal/replacement sequencing, never cascade
delete, source mutation or rewind. Required synchronous handoffs are atomic with
source finalization; otherwise the source remains explicitly pending/failed. Every
later hop needs its own registered and authorized contract, preventing uncontrolled
chains. Activation is per-contract and separately authorized after focused
PostgreSQL isolation, concurrency, idempotency, reversal, reconciliation and
recovery evidence. This decision is architecture-only: it authorizes no adapter,
producer, resolver, event, signal, job, posting, stock movement, Treasury proposal
or activation. P5-S05 remains prohibited from implementing any handoff.

### P5-D08 — P5-S05 first implementation slice

| Option | Consequence |
| --- | --- |
| **A — Internal RFQ foundation only (ACCEPTED WITH CLARIFICATION)** | A future separately authorized P5-S05 may implement Tenant/project-scoped RFQ drafts, approved request lineage, immutable issued versions/lines, addenda, closing and earliest permitted/scheduled opening boundaries, internal `BusinessParty` invitations, permissions, audit, locking, idempotency and focused tests. It creates neither an actual opening event/timestamp nor substantive No-Award, quote, award, portal or downstream behavior. |
| B — RFQ through award in one session | Too broad to validate confidentiality, SoD, correction and migration independently. |
| C — Start with supplier invoice/match | Violates delivery order and lacks sourcing/PO-change authority. |

**Decision:** **P5-D08 = A — ACCEPTED WITH CLARIFICATION (2026-10-02).** P5-S05
is prospectively limited to Tenant/project-scoped RFQ drafts, approved purchase-
request lineage, immutable issued versions and line snapshots, addenda, deadlines,
internal `BusinessParty` invitations, permissions, audit, locking, idempotency and
focused tests. Issue creates its version and line snapshots atomically; addenda
create new effective versions and never modify predecessors. Existing purchase
requests, direct POs and receipts remain `legacy_direct`; no history is fabricated.

P5-S05 may persist the authoritative RFQ closing deadline and earliest permitted/
scheduled opening boundary, but no actual bid-opening event or actual opening
timestamp. Manual closure cannot move that boundary earlier. P5-S05 implements no
substantive No-Award decision; any future No-Award belongs to the later sourcing/
evaluation/award slice with its own permissions, reason evidence and audit.
Invitation records imply no external delivery without retained proof.

No quote envelope/content/attachment/price/qualification/submission/opening,
comparison, evaluation or award is included. No portal, authentication, external
principal, email/SMS/provider, outbound integration, DMS expansion, quote storage,
downstream handoff or policy inference is included. `BusinessParty` remains the
sole supplier identity; only IRR is active. Acceptance requires the specified
focused PostgreSQL Tenant/isolation, permission, immutability, idempotency,
concurrency, relationship, legacy-compatibility and migration rollback/reapply
evidence. This decision does not authorize implementation; P5-S06+ remains
unauthorized.

## 9. Conditional P5-S05 implementation contract

This contract was executed after separate explicit Product Owner authorization of
P5-S05 on 2026-10-02. Acceptance of P5-D08 alone did not authorize implementation.

**Objective if separately authorized:** implement the internal RFQ foundation
described by accepted P5-D08 option A, ending at controlled RFQ issue, internal
invitation, addendum, deadline, closure and cancellation structures.

**Included:**

- tenant/project-scoped RFQ aggregate with UUID, organization-unique number,
  approved request/line lineage, terms, authoritative closing deadline, earliest
  permitted/scheduled opening boundary and explicit version, but no actual opening
  event or actual opening timestamp;
- immutable issued RFQ version and line snapshots; append-only addendum/version;
- tenant-local `BusinessParty` invitations with state/delivery metadata but no
  supplier authentication or outbound-provider integration;
- dedicated permission codes, registry/default grants following approved P5-D01,
  object-scope enforcement, service-layer transactions/locking and audit actions;
- registered workflow commands only where useful; domain services remain
  authoritative;
- focused model/service and integration tests for lifecycle, immutable versions,
  idempotent issue, concurrency, tenant/project/party scope, permissions/SoD,
  addendum/cancel evidence and legacy request/PO/receipt regressions;

**Excluded:** quote envelope, content, attachment, price, qualification, submission,
actual opening event/timestamp, evaluation/comparison, award or substantive
No-Award; PO creation/change behavior; receipt/service-acceptance changes;
supplier invoice/match; portal/external principal/authentication; email/SMS/
provider delivery; background jobs; UI; new DMS link type/schema or quote storage;
Project Cost/AP/GL/Treasury/Inventory adapters; data backfill/cutover; policy-value
inference; activation; and removal or reinterpretation of existing Procurement
records. UI remains deferred to its mapped P5 sessions.

**Acceptance criteria:**

1. Every write and read is Tenant-scoped; request/project/party/line relationships
   reject cross-Tenant and cross-project data.
2. Permissions and object scope deny by default at view and service boundaries;
   approved issue/override SoD is rechecked inside the locked transaction.
3. Issued versions/lines/invitations and transition evidence are immutable; an
   addendum creates a new effective version and retains its predecessor. Issue
   creates the immutable version and line snapshots atomically.
4. Issue is idempotent by stable occurrence and payload; conflicting retries and
   concurrent issue attempts fail closed without duplicate versions/invitations.
5. Cancellation/withdrawal requires reason and retains notification/delivery
   status without erasing prior evidence; delivery is not asserted without retained
   proof. Closure cannot move the earliest permitted opening boundary earlier and
   creates neither an actual opening timestamp nor a substantive No-Award decision.
6. Existing direct requests, POs and receipts behave unchanged and require no
   fabricated sourcing lineage.
7. No quote, award, financial, cost, stock, invoice, payment or portal fact is
   created; no producer/handoff is registered.
8. Targeted tests, `manage.py check`, migration-drift check, Ruff on changed Python,
   and documentation/link/whitespace checks pass. Focused PostgreSQL Tenant/
   isolation, permission, immutability, idempotency, concurrency, relationship,
   legacy-compatibility and migration rollback/reapply tests are required at the
   implementation acceptance checkpoint.

## 10. Dependencies, risks and explicit non-goals

Dependencies are separate explicit P5-S05 authorization; current tenant/membership
and project scope services; Parties supplier-role integrity; Workflow publication
and atomic command behavior; DMS object/version authorization if linked; and an
approved permission/default-grant design. Future handoffs additionally depend on
approved PO change, service acceptance, supplier-invoice/match, precision/tax,
Project Cost source-contract, AP source/posting, Inventory custody/value and
Treasury proposal contracts.

Primary risks are premature price disclosure, privilege concentration in small
Tenants, biased post-close correction, loss of supplier-attributed originals,
ambiguous award-to-PO lineage, duplicate/partial quantity consumption,
cross-Tenant party/document leakage, false downstream success, dual sources of
truth and fabricated legacy history. The controls above fail closed; they do not
claim those risks are operationally resolved before implementation and review.

Explicit non-goals are P5.2 portal/external identity, supplier onboarding UI or
support operations, subcontractor claims, qualification scoring, public/network
discovery, CRM, supplier invoice, match/tolerance execution, PO change, service
acceptance, stock receipt, Project Cost fact, AP obligation, journal, payment
proposal/cash movement, provider integration, background processing, migration/
backfill, pilot, production activation and removal of legacy fields.

## 11. Gate and exact next action

P5-S01–S08 are complete. P5-S05 added only the section 9 internal RFQ foundation:
tenant/project RFQ drafts, approved-request/line lineage, immutable issue/addendum
snapshots, deadline boundary, internal `BusinessParty` invitations, permission and
audit controls. P5-S06 adds only sealed internal `QuoteEnvelope` and immutable
`QuoteRevision` capture metadata, linked to the effective invitation/RFQ version,
with source/receipt time, SHA-256 integrity evidence, idempotency and
supersession/withdrawal lineage. It stores no prices, terms, attachments,
qualifications or other commercial content and provides no opening or reveal path.
P5-S07 adds only the immutable metadata close-custody manifest described below.
P5-S08 adds only the bounded, quarantined and version-pinned supplier package custody
described in section 12, without altering that manifest. These tranches implement no
opening/reveal, admissibility, comparison, evaluation, award, portal, downstream
handoff, backfill or production activation. P5-S09+, every downstream handoff and
P5.2 remain unauthorized.

### P5-S05 acceptance and migration review

The clean PostgreSQL migration path was verified from zero, and P5-S05 migration
rollback/reapply passed. The focused RFQ/Procurement PostgreSQL suite passed with
tenant scope, permission denial, immutable issue snapshots, idempotent issue and
concurrent identical issue coverage. Migration drift, `manage.py check` and Ruff
also passed.

The reported duplicate-table blockers required no schema deletion or migration
rewrite. `DocumentProcessingAssessment` is a current Documents target record,
owned by `documents.0007`, used by document availability/processing services and
tests, and recorded in the target domain/data model. `ChequeInstrument` is a
current Treasury target record, owned by `treasury.0001`, used by Treasury
lifecycle, clearing/bounce services, permissions and tests, and recorded in the
target domain/data model. Each has one current model and one owning `CreateModel`.
The earlier duplicate physical tables were artifacts of interrupted scratch
migration commands that had created schema before their migration bookkeeping
completed. No legacy dependency, model or table was removed.

### P5-S06 acceptance

P5-S06 uses tenant-local `BusinessParty` attribution only: no portal or external
supplier principal is created. `QuoteEnvelope`, `QuoteRevision` and immutable
transition evidence preserve the RFQ, invitation and effective RFQ/addendum version,
capturing actor, source channel/reference, supplier-provided timestamp where
available, system receipt timestamp, SHA-256 fingerprints, eligibility placeholder,
and supersession or withdrawal history. There is intentionally no persistence or
rendering path for commercial quote material; pre-opening confidentiality therefore
fails closed at the data boundary rather than relying on UI concealment.

The clean PostgreSQL migration path was verified from zero, and the P5-S06
migration rollback/reapply passed. Focused PostgreSQL quote/RFQ/Procurement tests
passed tenant scope, permission denial, immutable revisions, idempotent capture,
supersession/withdrawal and concurrent-identical-capture coverage. Migration drift,
`manage.py check` and Ruff also passed. P5-S06 is accepted; P5-S07 was subsequently
authorized and completed under the bounded contract recorded below.

### P5-S07 acceptance

P5-S07 replaces the earlier placeholder close operation with explicit synchronous
custody closure under the dedicated object-scoped `rfqs.close_custody` permission.
The permission is catalogued but granted to no default role; Tenant Owner, Admin and
platform status provide no bypass. Closure is permitted only at or after the
effective issued RFQ version's authoritative deadline and transactionally locks and
revalidates the RFQ, effective version, invitations, quote envelopes and revisions.

One immutable metadata-only `RFQCloseManifest` and one entry per effective-version
invitation record the stable idempotency key, payload fingerprint and exact custody
snapshot. An entry selects a revision only when it is timely, formally submitted,
non-withdrawn, non-superseded and tied to that effective invitation/version. Captured
but unsubmitted, withdrawn, superseded, late and absent evidence remains retained but
excluded. Later captures remain retained late evidence and can never mutate or
supplement the finalized manifest. PostgreSQL enforces at most one active submitted
revision per quote envelope. Closure creates no opening/reveal or commercial access,
admissibility, comparison, evaluation, award, No-Award or downstream fact.

Focused PostgreSQL closure/RFQ/quote tests passed permission denial, Tenant isolation,
deadline, immutability, idempotency, effective-selection/exclusion, post-close capture,
concurrency, rollback and regression coverage. P5-S07 migration rollback/reapply,
migration drift, Django checks and Ruff also passed. P5-D01's future distinct-user
requirements for reveal and award approval remain unchanged except for the later
narrowly scoped P5-S11 sourcing-only award self-finalization supersession; closure
adds no new distinct-human rule. P5-S08 was subsequently authorized and completed only under the
bounded contract in section 12. At the P5-S07 acceptance boundary P5-S09 remained
unauthorized; section 13 records its later separate authorization and acceptance.
P5-S10 is subsequently authorized, implemented, PostgreSQL-verified and Product
Owner accepted under the separately accepted
[P5-S10 decisions](P5_S10_PRODUCT_OWNER_DECISIONS.md). P5-S11 is subsequently
implemented, PostgreSQL-verified and Product Owner accepted under its
[P5-S11 decision packet](P5_S11_PRODUCT_OWNER_DECISION_PACKET.md); its scoped
award self-finalization supersession of P5-D01 is recorded in section 8.

## 12. P5-S08 sealed commercial-content custody decisions

The following Product Owner decisions originally prepared the bounded P5-S08 contract
and now govern its separately authorized implementation. They do not authorize
opening/reveal, admissibility, comparison, evaluation, award, No-Award, portal
capability, downstream handoff, production activation or any P5-S09+ work.

### P5-S08 Decision 1 — Typed DMS linkage

**Decision:** **A — ACCEPTED (2026-10-02).** Procurement owns an immutable,
one-to-many `QuoteRevisionEvidence` relationship. Each `QuoteRevision` must have
exactly one required `supplier_original` evidence item and may have zero or more
subordinate `supplier_attachment` items. Multiple files are never equivalent primary
supplier submissions. Every evidence row pins the exact immutable `Document` and
`DocumentVersion`; the evidence type, quote-revision identity, document identity and
document-version identity become immutable once custody accepts them.

Procurement owns quote/revision business meaning, evidence type and sourcing lineage.
Documents/DMS owns bytes, hashes, version integrity, quarantine, retention, legal
holds and storage lifecycle. Generic `DocumentLink` and generic document-context
linkage are prohibited for sealed quote evidence. No P5-S08 evidence link grants
preview, download, search, export or any other content visibility.

### P5-S08 Decision 2 — Permitted sealed evidence and commercial data

**Decision:** **A — ACCEPTED (2026-10-02).** P5-S08 accepts only immutable sealed
DMS evidence for the supplier submission package: the primary quote/proposal, price
or bill schedule, commercial terms, and currency, tax, freight, payment, delivery
and validity information; qualification/compliance and alternate-offer annexes; and
supporting supplier attachments. It creates no separately modeled price, total,
currency, tax, freight, payment-term, delivery, validity, qualification, alternate
or similar commercial fields.

Before P5-S09, there is no OCR, text extraction, indexing, preview, derivative
generation, content search, comparison preparation, normalization or human-readable
commercial metadata. Supplier-provided filenames and document titles are sealed
metadata and are never human-visible before authorized opening. Only neutral,
system-generated evidence identifiers or sequence labels may be exposed. MIME type,
byte size, integrity/hash status and quarantine/processing state may be retained only
as required technical custody/security metadata and must not expose commercial
meaning. Qualification and alternate evidence is retained source evidence only; it
gains no P5-S08 admissibility, eligibility, scoring or evaluation meaning. P5-S09 is
the first session that may authorize human reveal and interpretation.

### P5-S08 Decision 3 — File policy, validation and quarantine

**Decision:** **A — ACCEPTED (2026-10-02).** P5-S08 has code-owned, non-tenant-
configurable limits: exactly one `supplier_original` of at most 25 MiB; zero to 20
`supplier_attachment` items, each at most 25 MiB; and at most 100 MiB for the entire
sealed package per `QuoteRevision`. Future configurability requires a separately
approved policy contract.

Only PDF, DOCX, XLSX, CSV, JPEG and PNG are allowed. DOCX and XLSX must validate as
OOXML containers and are not rejected merely because their physical container is ZIP.
Generic archives, executables, macro-enabled Office formats including XLSM, legacy
binary Office formats, embedded-script formats and every unapproved type are rejected.
Validation checks extension, declared MIME type, detected/signature type, size, item
count, package total and applicable structural validity; extension/MIME/signature
disagreement fails closed.

Validation failure or expected-byte-hash mismatch creates no accepted
`QuoteRevisionEvidence` link and retains only redacted technical audit evidence. A
byte-valid upload enters unavailable/quarantined custody until authoritative security
processing records a clean result. Malware, processing failure and unknown/unavailable
security state retain inaccessible quarantined evidence; it cannot be opened in P5-S09
without later clean-processing evidence. A post-write integrity/hash mismatch fails
closed and never produces a usable sealed link. Security processing cannot alter the
supplier-original bytes; any inspection artifact is separate. Supplier filenames,
titles, contents and commercial metadata remain sealed even after technical validation.
P5-S08 adds no preview, rendering, spreadsheet interpretation, CSV execution, OCR,
extraction or other human-readable content processing.

### P5-S08 Decision 4 — Retention and holds

**Decision:** **A — ACCEPTED (2026-10-02).** P5-S08 introduces the code-owned
`sealed_supplier_quote_evidence` retention classification. It defines no numeric
retention period and implements no deletion, destruction, purge, automatic disposal
or disposition workflow for sealed quote evidence. Evidence remains retained and
non-disposable until a separately approved retention/disposal policy defines the
applicable legal, contractual, jurisdictional and operational rules. P5-S08 must not
infer a seven-year or any other duration, and generic Documents retention classes must
not silently govern this evidence.

Withdrawal, supersession, RFQ cancellation, future No-Award, quote ineligibility and
later sourcing decisions never delete, replace, detach or relax retention of original
evidence. Immutable `QuoteRevisionEvidence` linkage remains preserved; unlinking is
not a substitute for deletion or disposal. Documents/DMS owns legal, audit,
investigation and other approved holds; those holds block any future disposition.
Applying or releasing a hold cannot alter supplier-original bytes, QuoteRevision
lineage, hashes or historical custody evidence. A later separately authorized
retention/disposal contract must define duration, legal authority, hold release,
disposal approval, destruction evidence and jurisdiction-specific requirements.

### P5-S08 Decision 5 — Pre-production storage boundary

**Decision:** **A — ACCEPTED (2026-10-02).** Protected local/filesystem storage is
permitted only for the current pre-production P5-S08 environment. This acceptance
makes no production-readiness, production-activation, infrastructure, durability,
availability, disaster-recovery, object-storage, key-management or operational-support
claim. Passing P5-S08 tests on this backend accepts only the application-level
sealed-custody contract; it authorizes neither production activation nor external
supplier access.

Application and domain code must use stable Documents/DMS and `DocumentVersion`
identities, never filesystem paths as business identities. Physical location remains
an implementation detail, so a backend migration cannot alter evidence identity,
supplier-original hashes, `QuoteRevisionEvidence` lineage or historical audit evidence.
Direct filesystem access by ordinary users, administrators, Procurement users, support
personnel and application UI is prohibited; all access is mediated by the approved
Documents/DMS custody and authorization boundary. Supplier-original bytes, immutable
hashes, quarantine state, retention classification and hold state remain authoritative
regardless of backend. P5-S08 adds no public/static-media exposure, predictable direct
file URLs, generic download route or filesystem browsing. Backup, encryption at rest,
key custody, replication, disaster recovery, production object storage, production
malware-processing infrastructure and production operational controls remain separately
gated future decisions.

### P5-S08 Decision 6 — Custody permission and pre-opening confidentiality

**Decision:** **A — ACCEPTED (2026-10-02).** P5-S08 introduces
`rfqs.custody_sealed_evidence`, a dedicated Procurement capability for the synchronous
sealed-evidence intake operation only, scoped to the explicitly authorized
RFQ/QuoteRevision. It grants no content-view, preview, download, export, search,
derivative, reveal or interpretation authority; it has no generic/default-role grant.
An actor needs an explicit active tenant role/permission grant plus applicable
RFQ/project/object scope. Owner, tenant Admin, platform identity, superuser status,
uploader/capturing actor, support personnel, workflow position, generic Documents
permissions and UI visibility do not bypass it, and custody possession does not allow
the actor to retrieve content after intake.

Before P5-S09, `documents.view`, `documents.download`, generic admin interfaces,
linked-document contexts, search/index APIs, exports, previews, thumbnails,
derivatives, caches, logs, notifications and indirect document relationships cannot
expose sealed content. Supplier filenames and titles remain sealed. Only neutral
system-generated evidence identifiers and strictly necessary non-commercial technical
state may be exposed. P5-D02 remains authoritative: no human content access exists
before separately authorized protected opening. P5-D01 break-glass creates no
pre-opening exception; any future exception requires separately approved Product Owner
policy. P5-S08 adds neither `view_confidential`, reveal, admissibility nor an
equivalent permission.

Permission checks occur inside the authoritative custody transaction and independently
revalidate tenant, membership, object scope, RFQ/QuoteRevision relationship, lifecycle
state and applicable policy. Successful and denied attempts are audited without
recording or leaking sealed commercial content.

### P5-S08 Decision 7 — Integrity and attribution

**Decision:** **A — ACCEPTED (2026-10-02).** The P5-S06 `QuoteRevision` fingerprint
and the DMS `DocumentVersion` byte hash are distinct controls and must never be
conflated. Each accepted immutable `QuoteRevisionEvidence` pins the exact
`QuoteRevision`, immutable `DocumentVersion`, canonical immutable `DocumentVersion`
byte hash, P5-S06 revision fingerprint effective at custody acceptance, evidence type,
source channel, receiving/capture actor, and authoritative server receipt and custody
timestamps. Procurement owns supplier-evidence designation, sourcing lineage, capture
attribution and custody-event meaning. Documents/DMS owns immutable bytes,
document/version identity, canonical hashes, technical processing history, quarantine
state and storage lineage.

An expected byte hash is optional, but when supplied by an approved capture protocol it
must exactly equal the canonical stored `DocumentVersion` hash or custody acceptance
fails closed. A supplier-declared or externally provided hash never becomes
authoritative merely because it is supplied. Its absence never weakens the mandatory
canonical DMS hash. Receipt/custody timestamps cannot modify, replace, reinterpret or
backdate P5-S06 formal-submission time or P5-S07 cutoff evidence. The sole P5-S08
source channel is `internal_custody_capture`; no portal, supplier-authenticated upload,
external API submission, email ingestion, provider integration or other external source
channel is introduced.

Correction never overwrites accepted evidence. Any future replacement or corrective
evidence needs separately defined immutable lineage. Audit events retain the applicable
identities, hashes, actors, timestamps, source channel and acceptance/failure outcome
without exposing sealed content or supplier filenames/titles.

### P5-S08 Decision 8 — Atomic custody and idempotency

**Decision:** **A — ACCEPTED (2026-10-02).** P5-S08 uses one synchronous,
authoritative custody use case. Inside its transaction it locks and revalidates tenant
and active membership; RFQ and effective RFQ version; invitation; quote envelope and
exact `QuoteRevision`; `rfqs.custody_sealed_evidence`; project/object scope; lifecycle
state; evidence type and multiplicity; and applicable integrity and custody rules.
Accepted `DocumentVersion`, immutable `QuoteRevisionEvidence` linkage and redacted
audit evidence commit as one authoritative business outcome. Authorization or
relationship failure, expected-hash mismatch, validation failure, inability to establish
the required quarantine/processing record, audit failure or any other invariant failure
creates no accepted evidence link.

A byte-valid successful request commits immutable DMS version and Procurement evidence
link in quarantined/unavailable state only; it neither records a clean security result
nor grants visibility. Temporary protected bytes may precede acceptance but have no
business identity or `QuoteRevisionEvidence` lineage, are unaddressable through
application, DMS, admin, download, preview and generic document routes, and are cleaned
up on acceptance failure. If immediate cleanup fails, the bytes remain non-addressable
and outside authoritative custody/business lineage, recoverable only through a bounded
technical cleanup mechanism; that failure is audited without content exposure. An
abandoned temporary object is never promoted to an accepted Document or evidence record.

Every evidence-item attempt needs a caller-provided idempotency key, scoped to that
intended custody operation rather than the entire `QuoteRevision`. Its sealed technical
payload fingerprint includes stable target identities, evidence type, applicable
evidence-item identity/slot, canonical document/version/hash inputs, supplied expected
hash and required technical attributes, but never supplier content, filenames, titles
or other commercial metadata. The same key and fingerprint returns the original
accepted result without another `DocumentVersion` or link; a different fingerprint for
the same key fails closed and creates no additional accepted evidence. Concurrent
equivalent requests converge on one authoritative accepted result, while conflicting
requests fail without mutating it. Idempotency never collapses distinct legitimate
`supplier_attachment` items. All prior P5-S08 immutability, quarantine, pre-opening
confidentiality, retention, hash, permission and attribution decisions remain in force.

## Consolidated P5-S08 implementation contract — implemented and accepted

P5-S08 is limited to synchronous, pre-production sealed custody of supplier-original
commercial package bytes for an existing P5-S06 `QuoteRevision`; it follows the P5-S07
immutable metadata-only close manifest and precedes P5-S09 protected opening/reveal and
admissibility. It creates no opening, reveal, human content access, admissibility,
comparison, normalization, evaluation, award/No-Award, portal/P5.2, external supplier
channel, UI, scheduler/background closure, commercial field model, production activation
or downstream procurement/financial handoff.

1. **Ownership and immutable links.** Procurement owns a dedicated immutable,
   version-pinned `QuoteRevisionEvidence` relationship, not generic `DocumentLink` or a
   generic document context. An accepted package has exactly one required
   `supplier_original` primary artifact and zero to 20 subordinate
   `supplier_attachment` artifacts; multiple files never become equivalent originals.
   Every link pins exact `QuoteRevision`, `Document`, and immutable `DocumentVersion`.
   Evidence type and all pinned identities become immutable on acceptance. Procurement
   owns meaning, type and sourcing/capture lineage; Documents/DMS owns bytes, versions,
   hashes, quarantine, retention, holds and storage lifecycle.
2. **Sealed content and visibility.** Only supplier package files are accepted:
   primary quote/proposal, price/bill schedule, commercial terms, currency/tax/freight/
   payment/delivery/validity information, qualification/compliance and alternate-offer
   annexes, and supporting attachments. They remain documents only: P5-S08 adds no
   structured commercial fields, OCR, extraction, indexing, preview, rendering,
   derivatives, search, comparison preparation, normalization or interpretation.
   Filenames and titles are sealed; pre-P5-S09 exposure is limited to neutral evidence
   identifiers/sequence labels and necessary non-commercial technical state.
3. **File acceptance and quarantine.** Accept only PDF, DOCX, XLSX, CSV, JPEG and PNG;
   validate extension, declared MIME, detected/signature type, size, count, aggregate
   package size and applicable structural validity. DOCX/XLSX validate as OOXML even
   though containerized as ZIP. All disagreement fails closed; generic archives,
   executables, XLSM, legacy binary Office, embedded-script formats and all other types
   are rejected. One original is at most 25 MiB; each attachment is at most 25 MiB; the
   package is at most 100 MiB. Limits are code-owned and not tenant-configurable.
   Validation or hash failure yields no accepted link and only redacted technical audit.
   Byte-valid accepted evidence starts quarantined/unavailable. Malware, processing
   failure or unknown security state remains inaccessible; only a later authoritative
   clean result can make it eligible for a separately authorized P5-S09 decision.
4. **Retention and storage.** Apply the code-owned
   `sealed_supplier_quote_evidence` classification, not a generic Documents class.
   P5-S08 defines no duration and no deletion, destruction, purge, disposal or
   disposition. Withdrawal, supersession, cancellation, future No-Award, ineligibility
   and later sourcing decisions never detach, replace or relax evidence retention.
   Documents/DMS holds block future disposition without changing bytes, hashes or
   lineage. Protected local/filesystem storage is accepted only for pre-production;
   filesystem paths are not business identities, direct filesystem access and public or
   generic media/download paths are prohibited, and backend migration cannot change
   evidence identity, hashes, lineage or audit history. No production-readiness claim is
   made.
5. **Permission, integrity and attribution.** Add only the object-scoped
   `rfqs.custody_sealed_evidence` capability, with no default-role grant and no
   Owner/Admin/platform/superuser/uploader/support/workflow/generic-Documents bypass.
   It permits custody intake only and never subsequent retrieval. P5-D02 denies every
   human content path before P5-S09, including generic views/downloads, admin, indirect
   contexts, search, export, preview, thumbnail, derivative, cache, logs and
   notifications. Each link records its exact revision and version, canonical DMS byte
   hash, effective P5-S06 revision fingerprint, type, the sole source channel
   `internal_custody_capture`, receiving/capture actor and authoritative receipt/custody
   times. The fingerprint and hash are distinct. Expected hashes are optional but, when
   supplied by an approved capture protocol, must match exactly; external claims are not
   authoritative. Receipt time never alters formal submission or P5-S07 cutoff evidence.
6. **Atomicity, idempotency and audit.** Implement the accepted Decision 8 transaction,
   locking/revalidating all target and authorization state before acceptance. Commit
   `DocumentVersion`, quarantined custody record, immutable typed link and redacted
   audit together or accept none. Use evidence-item-scoped idempotency key and sealed
   technical payload fingerprint; exact repeats return the original result, conflicts
   fail closed, and concurrency preserves one accepted equivalent result without
   collapsing distinct attachments. Temporary failures retain no addressable business
   evidence and use bounded technical cleanup only.
7. **Acceptance evidence.** Provide focused PostgreSQL constraint and concurrency tests;
   migration rollback/reapply and migration-drift checks; tenant/object-scope and
   permission/no-bypass tests; immutability, fingerprint/hash, lineage and redacted-audit
   tests; content-denial tests for every listed indirect path; file-policy/OOXML/hash/
   quarantine tests; deadline/submission/cutoff regression tests as applicable;
   rollback, idempotency, conflicting-retry, concurrent-attachment and temporary-cleanup
   tests; Django check, Ruff and documentation/roadmap closeout. Tests must prove that
   post-acceptance evidence cannot supplement the P5-S07 manifest and that no P5-S09+
   capability is introduced.

### P5-S08 acceptance

P5-S08 implements only the consolidated contract above. Procurement now owns the
immutable `QuoteRevisionEvidence` link for one required `supplier_original` followed
by no more than 20 distinct `supplier_attachment` items. Each accepted item pins the
exact `Document`, `DocumentVersion`, quarantined `SealedDocumentCustody`, canonical
SHA-256 and effective P5-S06 revision fingerprint; Documents/DMS owns the protected
bytes and the code-owned `sealed_supplier_quote_evidence` classification.

The synchronous custody use case locks and revalidates the active tenant membership,
RFQ/project scope, effective RFQ version, invitation, envelope, exact submitted and
timely revision, immutable P5-S07 manifest entry and the dedicated
`rfqs.custody_sealed_evidence` permission inside one transaction. That permission has
no default-role grant and no Owner/Admin/platform/superuser/uploader/support bypass.
The transaction enforces the approved file signatures/MIME/extensions, OOXML
structure, 25 MiB item, 20-attachment and 100 MiB package limits; exact item retry is
stable, conflicts fail closed, and distinct concurrent attachments remain distinct.
The DMS version, quarantined custody row, typed Procurement link and redacted audit
commit together or none do. Protected temporary and rolled-back stored bytes are
removed without becoming addressable business evidence.

P5-D02 remains fail-closed. Generic Documents listing, detail, search, comparison,
version upload, archive, download, export, disposal and Admin paths exclude or deny
sealed evidence. Filenames, titles and content are absent from custody audit metadata;
accepted bytes remain unavailable and no preview, extraction, derivative, reveal or
human content route exists. P5-S08 neither supplements nor mutates the P5-S07 close
manifest and adds no admissibility, comparison, normalization, evaluation, award,
No-Award, UI, portal/P5.2, external channel, scheduler, production infrastructure,
downstream handoff or backfill.

Focused PostgreSQL tests cover permission/no-bypass and object/tenant scope, immutable
lineage, quarantine, redacted audit, PDF/OOXML/hash validation, exact and conflicting
idempotency, concurrent equivalent and distinct-item requests, code-owned limits,
P5-S07 manifest preservation, generic-content denial, rollback and protected-byte
cleanup. The three new migrations were rolled back and reapplied successfully;
migration drift, Django check and Ruff pass. This is application-level pre-production
acceptance only and makes no production-readiness or activation claim.

## 13. P5-S09 protected-opening disposition — implemented and accepted

The Product Owner accepted P5-S09-D01 through P5-S09-D06 in
[P5-S09 Product Owner decisions](P5_S09_PRODUCT_OWNER_DECISIONS.md). P5-S09 now
catalogues four default-ungranted capabilities and protected reveal classification.
The first valid opening request permanently freezes the exact P5-S08 package and
later custody cannot add, replace or relink evidence. A different active actor with
independent approval authority may atomically create one immutable opening event only
after locked tenant/project/object, effective-manifest, earliest-opening, SoD,
package-wide current CLEAN, stored-byte and hash revalidation.

Post-open content access requires active membership, project scope,
`rfq_quotes.view_confidential` and an active explicit revision grant created under
separate grant-management authority; self-grant and participant-derived access fail
closed. Revocation is append-only. The synchronous delivery service returns only one
exact pinned `DocumentVersion`, sanitizes response filename metadata, provides
attachment-only/no-sniff semantics, exposes no storage path or URL, and records
redacted successful and denied access. Generic DMS download, preview, rendering,
OCR/extraction/index/search/cache/derivatives, bulk export and application execution
remain absent. P5-S07's close manifest is unchanged; CLEAN has technical-openability
meaning only. Commercial admissibility is subsequently implemented by P5-S10 under
its separate accepted contract; break-glass remains absent.

Focused PostgreSQL tests cover tenant/object scope, no-bypass permissions, earliest-
opening boundary, exact permanent freeze, custody prohibition, SoD, immutable
opening evidence, CLEAN/hash/storage checks, request/approval idempotency and
concurrency, grant/self-grant/revocation, exact delivery, redacted access denial and
atomic audit rollback. P5-S05–S08 regression, migration rollback/reapply, migration
drift, Django check and Ruff pass. This is pre-production application acceptance,
not production readiness or activation. P5-S10 is subsequently implemented under
its separate accepted contract; P5-S11 is subsequently implemented,
PostgreSQL-verified and Product Owner accepted under its separate packet. P5.2 and
later work remain unauthorized.

### Proposed separate P5-S05 authorization text — not granted

> Authorize P5-S05 only, implementing the internal RFQ foundation defined in
> section 9 of this packet and accepted P5-D01 through P5-D08. Scope is limited to
> Tenant/project-scoped RFQ drafts; approved purchase-request and line lineage;
> immutable atomic issued versions and line snapshots; append-only addenda;
> authoritative closing deadlines and earliest permitted/scheduled opening
> boundaries without any actual opening event or timestamp; internal tenant-local
> `BusinessParty` invitation records; dedicated permissions and object scope;
> audit, locking, idempotency; legacy-direct compatibility; documentation closeout;
> and the specified focused PostgreSQL and migration rollback/reapply validation.
> Do not implement quote envelopes or content, attachments, prices,
> qualifications, submissions, actual opening, comparison, evaluation, award,
> substantive No-Award, portal/external identity or delivery, authentication,
> email/SMS/providers, UI, DMS expansion, quote storage, supplier invoice/match,
> PO/receipt/service-acceptance changes, Project Cost/AP/GL/Inventory/Treasury
> handoffs, policy inference, background work, data backfill/cutover or production
> activation. Preserve existing purchase requests, direct POs and receipts as
> `legacy_direct` without fabricated sourcing history. P5-S06 and later sessions
> remain unauthorized.
