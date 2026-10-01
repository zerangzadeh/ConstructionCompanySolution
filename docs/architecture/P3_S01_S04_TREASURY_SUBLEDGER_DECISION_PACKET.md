# P3-S01–S04 Treasury, Subledger, and Legacy Payment Decision Packet

**Prepared:** 2026-10-01

**Status:** D3-01 THROUGH D3-12 ACCEPTED; P3-S01–S11 COMPLETE

**Authority:** The Product Owner requested execution of P3-S01–S04 on 2026-10-01.
That request authorized the bounded evidence and design tranche. On 2026-10-01
the Product Owner accepted D3-01 through D3-08 = A, D3-09 = A-Revised, and D3-10
through D3-12 = A. This closes P3-S01–S04 only. It does not authorize P3-S05
implementation, register an operational Accounting producer, migrate a Tenant, or
activate bank integration. A separate Product Owner authorization on 2026-10-01
subsequently authorized and completed P3-S05–S11. A further bounded Product Owner
authorization completed P3-S12–S17 under its separate
[implementation contract](P3_S12_S17_IMPLEMENTATION_CONTRACT.md); the original
decision record below remains intact.

### P3-S05–S11 implementation closeout

The new `treasury` app owns Tenant accounts, mapping versions, movements and legs,
cheque instruments, immutable transition/posting evidence and retained
Treasury-to-GL reconciliation. The registered synchronous producer
`treasury.movement.posted.v1` posts only through Accounting, pins source/version/
line/event/rule/mapping/policy/period identities, and uses linked Accounting
reversal for correction. Dedicated permissions, default grants, masking, active
Tenant/membership/scope checks, explicit effective Self-Approval policy, protected
Accounting maker-checker separation, deterministic Tenant locking and idempotency
are enforced in services and constraints. Cheques affect bank cash only at
confirmed clearing; a post-clear bounce creates the linked cash and journal
reversal.

Migrations are `accounting.0011`, `organizations.0059`, `audit.0041`, and
`treasury.0001–0003`. Six focused PostgreSQL tests passed. TINF-01 was then
resolved at its root: `post_migrate` reconstructs system-owned authorization and
registered WorkflowType catalog rows after flush, while the official compatibility
bootstrap restores a missing system template without a test fixture. The three
previously blocked Accounting regressions and all 29 Accounting foundation tests
passed after that correction. The independent `MATERIAL_DOCUMENTS_LINK` registry
failure remains unchanged. No legacy Payment cutover/backfill, pilot, UI, statement import,
requests/scheduling/advances, AP/AR, bank integration, background processing,
multi-currency or tax/statutory behavior was added.

### P3-S12–S17 implementation closeout

The separately authorized P3-S12–S17 tranche delivered unscheduled payment
requests, exact posted-disbursement release, employee/vendor advance custody,
cash-return settlement, integrated protected correction and retained
advance-to-Treasury-to-GL evidence. It uses the existing D3-09 Self-Approval policy
and `treasury.movement.posted.v1`; no second posting producer or ledger was added.
Migrations are `treasury.0004`, `organizations.0060`, and `audit.0042`.

Nine focused PostgreSQL Treasury tests, three retained Accounting regressions and
focused permission/catalog checks passed. Scheduling/proposals, every numeric
threshold, non-cash substantiation, legacy migration/cutover, pilot activation,
statements, AP/AR, external integration, UI, background work and P3-S18+ remain
deferred/not authorized. `MATERIAL_DOCUMENTS_LINK` remains an independent known
registry issue.

## 1. Bounded four-session contract

| Session | Outcome | Acceptance evidence |
| --- | --- | --- |
| P3-S01 | Reconcile the P2 handoff, current legacy cash/settlement evidence, and Treasury/AP/AR authority; prepare the minimum decision set. | Sections 2–4 identify the current authority and every unresolved Product Owner choice without treating `Payment` as Treasury, AP/AR, or GL. |
| P3-S02 | Define target ownership, account/movement/instrument lifecycles, authorization, and the first Accounting producer boundary. | Sections 5–7 define one owner per fact, fail-closed policy inputs, immutable correction, SoD, and the source/version/line/idempotency/posting contract. |
| P3-S03 | Define the legacy `Payment`/allocation/claim-settlement containment and semantic transition. | Section 8 supplies expand → inventory/map → switch → validate → retain/rollback gates with no dual posting or fabricated history. |
| P3-S04 | Validate dependencies, rollout/recovery, reconciliation, and the executable S05 handoff. | Sections 9–11 name prerequisites, tests, stop conditions, exclusions, and the exact decisions required before implementation. |

| Item | Contract |
| --- | --- |
| Included | Treasury/AP/AR ownership; first bounded P3 capability; cash-account and movement structure; party-bank-profile boundary; cheque treatment; authorization/SoD; synchronous Accounting producer contract; legacy compatibility and transition; statement-import execution direction; reconciliation, rollout, rollback, and S05 handoff. |
| Excluded | Models, migrations, permissions/catalogue changes, UI, data backfill, producer registration, journal creation, bank/provider integration, file-format selection, numeric approval limits, AP/AR implementation, write-off activation, production cutover, and destructive removal/rename. |
| Direct evidence | `P2_S38_P3_HANDOFF_PACKET.md`; `ADR_P0_S04_ACCOUNTING_POSTING.md`; `Payment`, `PaymentAllocation`, and payment services/tests; Billing `ClaimSettlementAllocation` and settlement services/tests; legacy `financials` projections; current Accounting registry/posting/reconciliation controls; active domain/data/permission architecture. |
| Stop condition | Satisfied on 2026-10-01 by D3-01..D3-08 = A, D3-09 = A-Revised, and D3-10..D3-12 = A. P3-S05 remains unauthorized and may start only after a separate explicit implementation authorization. |

## 2. Verified current evidence

1. `Payment` is an immutable-after-create Tenant/project receipt or disbursement
   record with positive Decimal amount, date, method, optional party/contract/phase,
   organization-unique number, `posted -> void` lifecycle, reason/actor/time evidence,
   document links, and append-only audit events. It has no cash/bank-account,
   currency, fiscal-period, source-version, Accounting rule, journal, cheque
   lifecycle, bank statement, or clearing identity.
2. `PaymentAllocation` assigns part of one posted Payment to a same-Tenant,
   same-project contract under a locked cap. It is a contractual allocation, not a
   journal line or an AP/AR open-item settlement. Reversal preserves history.
3. Billing `ClaimSettlementAllocation` uses an active allocation of a posted
   receipt and validates Tenant/project/contract/party/capacity. Reversing or
   voiding the upstream allocation reverses dependent claim settlement evidence in
   the same transaction. No current AR obligation/open item exists.
4. The `financials` domain aggregates posted Payment amounts into a legacy project
   cash projection. It is not a cash ledger, subledger, Accounting statement, or
   reconciliation authority.
5. Payment writes are service-driven, permission-checked, audited, and row-locked
   for void/allocation operations. Current permissions (`payments.view/create/
   void/allocate`) and UI remain compatibility capabilities, not authorization for
   future Treasury accounts, sensitive bank data, release, clearing, or AP/AR.
6. Accounting is already the sole journal authority. Its immutable posted lines,
   source identity, rule/version evidence, Tenant coordination lock, correction,
   retained reconciliation, statement, and close controls cannot be bypassed by a
   P3 writer.
7. The Party domain has no implemented controlled bank-profile model. External
   counterparty bank facts and internal Tenant cash-account facts therefore remain
   separate missing prerequisites.

## 3. Preserved decisions and non-negotiable invariants

- Treasury owns internal bank/cash/petty-cash accounts, movements, instruments,
  statement evidence, clearing, and bank reconciliation. AP/AR owns obligations,
  open items, adjustments, settlement allocations, aging, and subledger
  reconciliation. Accounting alone owns journals and balances.
- A source document, cash movement, contractual allocation, AP/AR settlement,
  bank match, and journal line are distinct facts. Links reconcile them; none is
  duplicated to simulate another authority.
- Every P3 record, relationship, query, command, identifier, uniqueness constraint,
  and retained reconciliation is Tenant-scoped. Project/site scope further
  restricts linked operational context but never grants access to a cash account.
- Finalized movement, instrument, settlement, mapping, reconciliation, and posting
  evidence is immutable. Correction is a linked reversal/replacement or separately
  authorized adjustment; delete, in-place amount edit, and status rewind are
  prohibited.
- IRR is the only active monetary currency. Toman and FX behavior remain absent.
  Decimal precision and rounding use effective configured policy and fail closed
  when the required value/version is missing.
- A future producer is code-registered, synchronous, transactional, idempotent,
  and balanced. It pins source/version/line/event/rule identities and cannot select
  arbitrary accounts or post through signals.
- Positions, workflow assignments, role labels, Payment permissions, and UI
  visibility never grant Treasury/AP/AR authority. Active membership, Tenant
  status, business permission, applicable object scope, and effective approval/
  SoD policy are rechecked in the locked transaction.
- Existing Payment, allocation, claim settlement, document, actor, audit, number,
  void, and reversal history is retained until separately approved removal after
  migration, dependency removal, reconciliation, recovery, and retention gates.

## 4. Product Owner decision summary

The Product Owner accepted `D3-01=A` through `D3-08=A`, `D3-09=A-Revised`, and
`D3-10=A` through `D3-12=A` on 2026-10-01. The revised D3-09 binds Treasury to the
already accepted platform Self-Approval policy: Protected Operations are never
self-approvable; other Treasury business operations follow explicit, versioned,
scope-bound and audited platform/Tenant policy.

| ID | Decision | Accepted option | Binding consequence |
| --- | --- | --- | --- |
| D3-01 | First P3 capability | A | Starts with Treasury authority and direct cash/instrument facts before requests or AP/AR consume it. |
| D3-02 | Domain/app ownership | A | Keeps Treasury and AP/AR distinct while preserving legacy `payments` as compatibility evidence. |
| D3-03 | Account and object-scope structure | A | Uses one Tenant account master with explicit kinds, masking, and no project-owned cash silos. |
| D3-04 | Movement lifecycle and correction | A | Gives every cash event one immutable authority and one reversible finalization path. |
| D3-05 | Accounting producer contract | A | Activates posting only through a configured, synchronous, atomic, code-registered contract. |
| D3-06 | Legacy Payment disposition | A | Uses evidence-based per-row mapping/opening/exception outcomes and forbids bulk relabeling. |
| D3-07 | Compatibility consumer switch | A | Preserves Billing/document/audit lineage and prevents mixed old/new totals. |
| D3-08 | Party bank-profile boundary | A | Parties own external beneficiary facts; Treasury owns the Tenant's accounts. |
| D3-09 | Maker-checker and approval limits | A-Revised | Protected Operations never allow Self-Approval; Treasury business-operation Self-Approval is configurable by explicit platform/Tenant policy, with an independent checker mandatory when disabled or when an additional threshold applies. |
| D3-10 | Cheque recognition | A | Treats cheques as instruments; bank cash changes only on confirmed clearing. |
| D3-11 | Statement import execution | A | Starts with bounded idempotent synchronous imports; no unapproved queue/provider. |
| D3-12 | Rollout and rollback | A | Uses pilot/cutoff/reconciliation gates and forward correction after authoritative posting. |

## 5. S01/S02 ownership and structural decisions

### D3-01 — First bounded P3 capability

| Option | Consequence |
| --- | --- |
| **A — Treasury foundation first (recommended)** | P3-S05–S11 may implement Tenant bank/cash/petty-cash accounts plus direct receipts, disbursements, transfers, and cheque instruments. Requests/scheduling/advances remain S12–S17; statements/reconciliation remain S18–S22; AP/AR remains S23–S27. |
| B — AP/AR first | Creates obligations without the accepted settlement/cash authority and contradicts the current dependency order. |
| C — Relabel legacy Payment as Treasury | Preserves missing bank/currency/period/source-version facts and creates an unsafe authority shortcut. |

**Decision:** **D3-01 = A — ACCEPTED.**

### D3-02 — Domain and Django-app ownership

| Option | Consequence |
| --- | --- |
| **A — Separate native authorities (recommended)** | A new `treasury` app owns internal accounts, movements, instruments, bank evidence, and reconciliation. A later `subledgers` app owns both AP and AR obligations/open items/settlements with an explicit receivable/payable type. The existing `payments` app remains a compatibility boundary during transition. |
| B — Put all P3 facts in `payments` | Reuses a name but obscures cash versus obligation ownership and couples migration history to the target design. |
| C — Put P3 facts in `accounting` | Creates a competing source/ledger aggregate and violates the accepted authority boundary. |

**Decision:** **D3-02 = A — ACCEPTED.**

### D3-03 — Internal account structure and object scope

| Option | Consequence |
| --- | --- |
| **A — One Tenant account master with explicit kinds (recommended)** | Organization-owned account records use platform-closed `bank`, `cash`, and `petty_cash` kinds; retain stable code, IRR currency, effective status, sensitive identifiers, custodian where applicable, and versioned Accounting mapping. Project/site references classify a movement but never own or authorize the account. Dedicated Treasury permissions grant Tenant financial access; project/site grants only narrow linked movement context. Sensitive identifiers are masked unless a separate permission is held. |
| B — Project-owned cash accounts | Simplifies project reports but fragments Tenant cash authority and makes transfers/reconciliation ambiguous. |
| C — Reuse party bank profiles for internal accounts | Collapses counterparty identity into Treasury custody and cannot express cash/petty-cash control. |

Account activation, mapping change, suspension, and close require reasoned audited
services. Closing is allowed only after no pending instrument/import/reconciliation
work and a zero or explicitly transferred reconciled balance. Exact field/schema
design belongs to S05; no bank identifier is invented by this packet.

**Decision:** **D3-03 = A — ACCEPTED.**

## 6. S02 lifecycle, authorization, and Accounting decisions

### D3-04 — Movement aggregate, lifecycle, and correction

| Option | Consequence |
| --- | --- |
| **A — One movement aggregate with explicit legs (recommended)** | Receipt, disbursement, and transfer are kinds of one Tenant-scoped aggregate with stable source/version/event identity and explicit account legs. A transfer has balanced source/destination legs in one atomic record, never two unrelated transactions. Lifecycle is `draft -> submitted -> approved -> posted`; reject/cancel is pre-post only; correction of posted facts uses linked reversal and optional replacement. |
| B — Independent receipt/payment records for transfers | Risks one-sided transfer failure, duplicate cash, and difficult reconciliation. |
| C — Posted-on-create | Repeats the legacy control gap and cannot provide configured approval or posting validation. |

Every transition locks/re-reads the Tenant financial coordination boundary and the
aggregate, rechecks permission/SoD, and records actor/time/reason. Posted facts and
their legs are immutable. A retry with the same identity and payload returns the
existing result; a conflicting payload fails closed.

**Decision:** **D3-04 = A — ACCEPTED.**

### D3-05 — First operational Accounting producer

| Option | Consequence |
| --- | --- |
| **A — Registered posted-movement producer (recommended)** | `treasury.movement.posted.v1` becomes the first operational producer only after a separately authorized P3 implementation session supplies the accepted adapter and tests. Treasury approval and Accounting posting/finalization commit atomically through the Accounting service. The producer pins movement version, leg IDs, event identity, rule/mapping versions, IRR precision policy, fiscal period, dimensions, and resulting journal. |
| B — Finalize cash now and batch journals later | Creates an unreconciled authority gap and requires an unapproved asynchronous/outbox design. |
| C — Continue without GL integration | Makes native Treasury an independent financial ledger and violates P0-D02/P2. |

Configured mapping, not the producer, chooses accounts. Direct receipts and
disbursements use approved cash and clearing/unapplied roles; AP/AR application is
a later distinct event. Transfers use source/destination cash roles. Missing or
closed period, policy, mapping, dimension, permission, required approval/
separation, or precision blocks finalization. Reversal creates a linked Accounting
reversal exactly once;
it never edits the original journal. Cash-to-GL tie-out is mandatory before pilot
cutover and period close.

**Decision:** **D3-05 = A — ACCEPTED.** Producer registration and implementation
remain separately authorization-gated.

### D3-09 — Maker-checker, Self-Approval, and amount limits

| Option | Consequence |
| --- | --- |
| **A-Revised — Platform-policy-controlled Self-Approval (accepted)** | Maker-checker and Self-Approval remain consistent with the accepted platform policy. Protected Operations are never self-approvable. For other Treasury business operations, platform policy classifies whether Self-Approval is permitted and an authorized Tenant actor may configure it only where the platform permits. When Self-Approval is disabled or an additional approval threshold applies, an independent permissioned checker is mandatory. |
| B — Role-based approval | A role label or position becomes accidental authority and conflicts with the existing permission model. |
| C — Owner/Admin bypass | Breaks Protected Operations and maker-checker separation. |

Every Self-Approval classification, Tenant choice, approval-policy decision, and
actual use must be explicit, versioned, scope-bound, and auditable. No role,
Tenant Owner/Admin status, or missing configuration implies approval authority.
Self-Approval never supplies missing membership, permission, object scope, valid
domain state, or threshold authority. Versioned kind/account/amount thresholds
remain configurable; when a required policy or threshold configuration is absent,
the operation fails closed. Where the effective policy prohibits Self-Approval or
requires an additional approval, the checker must be a different active membership
with the required permission and applicable scope.

**Decision:** **D3-09 = A-Revised — ACCEPTED.** This revision supersedes the
packet's original always-independent-checker recommendation while preserving the
platform prohibition for Protected Operations and all explicit authorization,
policy, threshold, and audit requirements.

### D3-10 — Cheque cash recognition

| Option | Consequence |
| --- | --- |
| **A — Instrument first, cash on confirmed clearing (recommended)** | Incoming/outgoing cheques are distinct instruments with direction, controlled account, amount, due date, party, masked serial/reference, custody and append-only states. Issue/receipt does not itself claim bank cash movement; confirmed clear creates or finalizes the linked movement. Bounce/cancel preserves the instrument and uses linked reversal only when an earlier finalized effect exists. |
| B — Cash movement at issue/receipt | Requires an approved accounting/cash policy for uncleared instruments and can overstate available bank cash. |
| C — Store cheque as Payment method only | Cannot represent custody, due dates, presentation, clearing, bounce, replacement, or statement match evidence. |

The initial closed state catalogue is `draft`, `issued`/`received`, `delivered` or
`deposited` as applicable, `presented`, `cleared`, `bounced`, and `cancelled`, with
direction-specific transition validation. The separately authorized implementing
session may narrow names without changing the recognition rule. Post-dated cheque
accounting/statutory treatment remains
subject to professional review and configured posting policy.

**Decision:** **D3-10 = A — ACCEPTED.**

## 7. Party bank profile and statement-import decisions

### D3-08 — External party bank profiles

| Option | Consequence |
| --- | --- |
| **A — Party-owned verified profiles (recommended)** | Parties owns versioned/effective external beneficiary/source bank profiles. Treasury references an active verified profile but snapshots the used masked identity/version on the movement. Internal Tenant accounts remain Treasury-owned. Outgoing bank transfer to a party requires a verified active profile; cash and explicitly reviewed legacy exceptions do not fabricate one. |
| B — Copy party banking into every movement | Loses canonical identity and makes correction/revocation inconsistent. |
| C — Put party and internal accounts in one Treasury table | Conflates counterparty identity, custody, permissions, and reconciliation ownership. |

Sensitive bank values require separate view/manage permissions, masking in lists,
audit on access/change, no exposure in logs, and encrypted storage only through an
approved maintained mechanism. Exact verification source and retention policy are
production gates and are not invented here.

**Decision:** **D3-08 = A — ACCEPTED.**

### D3-11 — Statement import execution mode

| Option | Consequence |
| --- | --- |
| **A — Bounded synchronous import first (recommended)** | S18–S22 may add preview/accept import with file hash, provider/account/period identity, row identity, duplicate rejection, exact retained source evidence, and deterministic matching. Oversized/unsupported files fail closed. No Celery, Redis, live bank connection, or network callback is introduced. |
| B — Background import now | Requires separately approved queue/outbox/retry/operations ownership and a concrete workload. |
| C — Live bank integration first | Adds credentials, provider contracts, residency, availability, and reconciliation failure modes before the native boundary is stable. |

Provider/file formats, size limit, credentials, and live connectivity remain
separate Product Owner gates. This decision only fixes the initial execution
architecture so S05–S11 do not depend on unapproved asynchronous infrastructure.

**Decision:** **D3-11 = A — ACCEPTED.**

## 8. S03 legacy containment and transition decisions

### D3-06 — Per-row legacy Payment disposition

| Option | Consequence |
| --- | --- |
| **A — Evidence-based mapping register (recommended)** | Inventory every Payment, active/reversed allocation, dependent claim settlement, document link, audit event, and legacy projection use by Tenant and cutoff. Each legacy row receives exactly one immutable reviewed disposition: exact mapped Treasury fact, covered by accepted opening balance, retained unresolved exception, or explicitly excluded non-production/demo fact. |
| B — Bulk backfill every Payment as Treasury | Invents absent bank/currency/period/source-version evidence and can double count opening balances or journals. |
| C — Leave both writers active indefinitely | Allows the same economic event to appear in competing authorities and reports. |

An exact map requires matching Tenant, direction, amount, IRR basis, date/period,
cash account, party where applicable, source/version, status, void/reversal chain,
and supporting evidence. Contract allocation maps only to contractual allocation.
Claim settlement maps to AR allocation only after the exact AR obligation, party,
currency, capacities, and source lineage exist. Missing facts enter the exception
register; they are never guessed from method, name, number, notes, or report total.

**Decision:** **D3-06 = A — ACCEPTED.**

### D3-07 — Writer and consumer cutover

| Option | Consequence |
| --- | --- |
| **A — Tenant cutoff with compatibility readers (recommended)** | Before a Tenant cutoff, legacy writes continue under existing behavior and cannot post to the new producer. At accepted cutoff, new writes switch once to Treasury; old records become read-only compatibility evidence. Billing keeps exact PaymentAllocation/claim-settlement links until S23–S27 maps them. Documents/audit preserve original UUIDs. Each report reads either the reconciled legacy scope or the new authority for a period, never a mixed union. |
| B — Dual-write Payment and Treasury | Creates two source identities, ambiguous correction, and duplicate posting risk. |
| C — Immediate destructive replacement | Breaks current Billing, documents, reports, audit drill-through, and rollback. |

The mapping register retains old/new identifiers, cutoff, reviewer, evidence,
result hashes, and exception status. Legacy void/reversal after mapping must call
the accepted integrated correction service; it cannot bypass Treasury or GL.
`payments` model/field removal, URL rename, and historical deletion require a
later explicit contract after all dependencies and retention gates close.

**Decision:** **D3-07 = A — ACCEPTED.**

## 9. S04 reconciliation, rollout, and rollback decision

### D3-12 — Pilot, validation, and recovery

| Option | Consequence |
| --- | --- |
| **A — Tenant pilot with controlled forward correction (recommended)** | Select one Tenant only after configuration, source inventory, opening/mapping plan, permission/SoD setup, and dry-run reconciliation pass. Validate old/new counts and amounts, movement-to-journal links, void/reversal effects, allocations/settlements, cash-to-GL, and no mixed writer/report scope. Before authoritative posting, rollback may disable the new writer and restore legacy writes with retained evidence. After authoritative posting, journals and source facts remain; recovery uses forward correction or an accepted restored checkpoint, never history deletion or silent legacy reactivation. |
| B — All-Tenant cutover | Expands blast radius before the first migration/reconciliation evidence exists. |
| C — Roll back by deleting new records | Violates immutable financial history and Accounting correction rules. |

The Product Owner must later name the pilot Tenant, cutoff, opening-versus-replay
coverage, exact acceptance tolerances, restore point, operator, and go/no-go
reviewers. Production activation remains blocked by unresolved P0 recovery/provider
parameters and applicable professional/statutory review.

**Decision:** **D3-12 = A — ACCEPTED.**

## 10. S05 handoff — implementation not authorized

The decision prerequisite is satisfied, but the Product Owner explicitly did not
authorize P3-S05. If separately authorized later, its bounded first action is the
Tenant-scoped Treasury account foundation, not movement posting:

1. create the `treasury` app and account/status/masking service boundary;
2. add dedicated permission catalogue/default-grant decisions and audit actions;
3. enforce active membership, Tenant status, sensitive-data permission, and
   organization-scoped uniqueness/relationships in services and constraints;
4. add activation/suspension/close lifecycle with reason, actor, time, effective
   approval/SoD policy, and Accounting mapping validation, while leaving movement
   producer registration for the session that implements the complete D3-05
   contract;
5. add PostgreSQL tests for Tenant isolation, authorization/SoD, identifier
   masking, concurrent uniqueness, mapping/currency/policy failure, and immutable
   lifecycle evidence.

Minimum context for S05 is this packet, the P2 handoff, P3.1 roadmap subsection,
Accounting posting/permission patterns, Organization object-scope services, Party
master boundary, and current Payment compatibility tests. S05 must not add AP/AR,
statement imports, requests/advances, UI, bank networking, or a legacy backfill.

## 11. Acceptance record and explicit exclusions

P3-S01–S04 design acceptance is complete. The following implementation and
production gates remain:

- every implementation package must preserve the selected decisions, current
  Accounting authority, and P2 close/reconciliation controls;
- the implementation package must name each new permission, audit action, model
  authority, lifecycle transition, lock order, idempotency key, correction path,
  reconciliation, migration, rollback, and focused test;
- exact configured precision/rounding and posting mappings before financial
  finalization; missing values remain fail-closed;
- no production cutover until the pilot/cutoff/recovery and external review gates
  are supplied.

This packet does not authorize AP/AR write-off policy, payment scheduling,
advances, external bank APIs, background jobs, controlled export, multi-currency,
Toman, tax/statutory conclusions, destructive retention, a named pilot, numeric
approval limits, or P3-S05 application changes.
