# ADR P0-S04: Native Accounting posting and Treasury/AP/AR source contracts

**Date:** 2026-09-24. **Status: ACCEPTED AS TARGET ARCHITECTURE ON 2026-09-28;
P1-S14 GOVERNANCE CLOSED 2026-09-29; P2 VALUE/RELEASE GATES PRESERVED.**

P0-D02 approves native financial authorities; it does not approve this detailed
design. The Product Owner requested P0-S04 within the
[S03 handoff](../ROADMAP_EXECUTION_PLAYBOOK.md#compact-p0-s04-handoff).
This bounded proposal addresses PPC-02 and the interface to PPC-03. It prepares
the Accounting ADR and Treasury/AP/AR containment contract together; full Treasury
instruments, bank imports, AP/AR lifecycles and budget/CBS design remain later work.

## 1. Authority and current evidence

Planning authority: [Roadmap P0.1, P2 and P3](../../ROADMAP.md),
[accepted decisions and unresolved inputs](../ROADMAP_EXECUTION_PLAYBOOK.md#28-p0-s03-release-assumptions-and-s04-handoff),
[target domain boundaries](DOMAIN_MODEL.md#4-strategic-aggregate-boundaries) and
[target posting rules](DATA_MODEL.md#7-financial-posting-model).
The following is static code evidence, not new runtime validation:

| Current record or behavior | Direct evidence | Design consequence |
| --- | --- | --- |
| `Payment` holds organization/project, optional contract/phase/party, direction, amount, paid date, method/reference and void evidence; number is organization-unique. It has no explicit currency, bank-account or fiscal-period field. | [Payment model](../../apps/payments/models.py), `Payment`; [services](../../apps/payments/services.py), `create_payment`, `void_payment` | Cash evidence alone cannot identify bank ownership, currency, liability or GL recognition. Never infer these from method, display name or document number. |
| `PaymentAllocation` assigns cash to a contract; service locks the payment and caps active allocations. Reversal preserves amount and evidence. | Same model/services, `allocate_payment`, `_reverse_locked_payment_allocation` | Preserve contractual allocation separately from open-item settlement and journal lines. |
| Billing links an approved claim to an active allocation of a posted receipt; checks tenant/project/contract/party and both remaining capacities. Payment allocation reversal also reverses dependent claim settlements. | [Billing services](../../apps/billing/services.py), `_validate_settlement_context`, `allocate_progress_claim_settlement`, `reverse_claim_settlements_for_payment_allocation`; [settlement model](../../apps/billing/models.py), `ClaimSettlementAllocation` | Reuse exact settlement lineage; do not count the allocation and settlement as two cash events or invent AP from this receivable-only path. |
| Financial reports derive estimates, recorded expenses and posted cash totals. | [financials services](../../apps/financials/services.py), `_build_report`, `get_project_financial_report` | Preserve operational projections; they do not establish GL balances, accepted budgets or comprehensive actual cost. |
| Historical allocation reversal reasons were backfilled; Billing settlement migration depends on that history. | [payments 0005](../../apps/payments/migrations/0005_backfill_paymentallocation_reversal_reason.py), [billing 0005](../../apps/billing/migrations/0005_claimsettlementallocation.py) | Retain migrations, original audit history and historical-placeholder provenance; do not invent an original reason/actor. |

Existing test evidence to preserve includes
`test_payment_allocation_cannot_exceed_payment_and_reverses_on_void` in
[payments tests](../../apps/payments/tests.py), and
`test_reverse_and_payment_void_reverse_settlements_atomically`,
`test_settlement_service_denies_cross_tenant_claim_and_allocation` and
`test_concurrent_partial_settlements_cannot_exceed_claim_outstanding` in
[Billing tests](../../apps/billing/tests.py). These tests were inspected or located,
not executed in this documentation session. S01's project-total and authorization
findings remain applicable; this is not a repository-wide re-audit.

## 2. Proposed ownership and alternatives

| Owner | Authoritative facts | Boundary |
| --- | --- | --- |
| Operational domain | Finalized source/version, quantities, commercial calculation and applied terms/rules | Supplies eligible evidence; cannot write arbitrary GL lines or change posted history. |
| Accounting | COA, posting dimensions/mappings, fiscal periods, registered rule versions, proposals, balanced posted journals, reversals and close evidence | Sole GL authority; no signal-based posting or domain-local ledger. |
| Treasury | Cash/bank accounts, movements, instruments and clearing/bank reconciliation | Owns whether cash moved; neither bank match nor invoice status is a second cash transaction. |
| AP/AR | Obligations/open items, due dates, adjustments and settlement allocations | Owns outstanding amounts; neither source document nor journal is a settlement allocation. |
| Project Cost / reporting | Classified source/subledger/posting projections and their lineage | Separates budget, commitment, actual, forecast and paid cash; never posts a balancing plug. |

Retain native authorities with explicit application-service contracts in the
existing modular monolith. Rejected alternatives: promote `PaymentAllocation`
to a journal line (wrong semantics); let each domain maintain its own GL (competing
balances); replace the accepted native direction with an external financial
authority (would reopen D02 without authorization). External export may later
consume native facts under its own approved contract.

Build-vs-Reuse: use Decimal, Django ORM/transactions and PostgreSQL constraints and
locks for commodity mechanisms. Product-owned posting, close, settlement and
reconciliation rules require explicit domain services. No dependency, new app,
queue, external integration or physical schema is selected by this ADR.

## 3. Source identity and posting contract

Each registered producer supplies a validated contract, not arbitrary table names,
SQL, expressions or tenant-authored executable rules. Proposed mandatory fields:

| Contract field | Meaning and validation |
| --- | --- |
| Tenant and context | Organization resolved through authenticated membership; validate every source, party, project/site/phase/contract and dimension within that tenant and applicable project. Optional structures remain optional. |
| Source identity | Platform-registered source kind, UUID and immutable finalized version; explicit source-line references where lines feed amounts/dimensions. Manual/opening journals have their own durable source identity. |
| Event identity | Registered economic event kind and durable occurrence ID, such as recognition, cash movement, settlement, adjustment or reversal. Distinct occurrences require real business evidence, not a fresh random retry ID. |
| Financial evidence | Effective date, requested accounting date, explicit currency and Decimal amounts/precision, party and relevant dimension snapshots, applied commercial/regulatory versions, source finalization actor/time. |
| Accounting selection | Accounting selects and pins the approved posting-rule and mapping versions; records any approved currency conversion/rounding inputs. The producer cannot choose arbitrary accounts to bypass the registry. |
| Causality | Original source/event/journal for correction, reason, actor, request correlation and approval/work-item evidence when applicable. Human document numbers are display identifiers. |

Proposed business uniqueness is `(organization, source_kind, source_uuid,
source_version, event_kind, occurrence_id)`, enforced in the database. Rule version
is pinned evidence, **not** a way to obtain a new business key and post the same
event again after a rule upgrade. A stable retry key resolves to this identity.
Same key and same canonical payload returns the recorded result after authorization;
same key with changed payload is a conflict. Concurrent identical requests yield
one result. A changed source version is eligible only through the producer's
revision/correction policy; it cannot bypass reversal of an already recognized fact.

Validate the live source/version and status at the service boundary; freeze the
accepted payload and material inputs/outputs. Use explicit domain links or a
constrained registered source link with tenant/version validation, never an
unrestricted generic reference. Missing mapping, currency, source eligibility or
required context blocks posting with a traceable validation result. It must not
silently use a default account, current master value or assumed legal rate.

## 4. Lifecycle, atomicity and authorization

Proposed journal lifecycle: `proposed -> posted` or `proposed -> rejected/cancelled`.
Approval, if required, belongs to the registered workflow; no second approval
engine. Rejected/cancelled proposal history is retained. Posting assigns the final
organization-scoped number and freezes lines, source/rule versions and dimensions.
Correction of a posted entry creates a separately numbered linked reversal and,
when needed, replacement; the original entry/lines remain intact. Reversal status
is derived from immutable links, not permission to edit the original.

Accounting service validation must establish debit/credit equality under the
approved currency/precision policy, valid active accounts/dimensions, an open
period, a still-eligible source and complete authorization. Multi-currency
balancing and FX rules are gated by Q01, not implied by a single sum across currencies.

For future integrated financial actions, lock/re-read the relevant period control,
source, obligation, cash capacity and posting identity in a documented consistent
order. Recheck membership, tenant status, permission, object scope and separation
inside `transaction.atomic()`. Commit the financial source transition, AP/AR or
Treasury effects, journal, posting result, workflow completion where applicable,
and audit evidence together. An audit/ledger failure rolls the operation back.
Deterministic lock order and deadlock retry policy require tests during implementation.

An operational source may already have finalized before financial acceptance;
that fact remains owned by its domain. Its missing/rejected posting stays visible
as a reconciliation exception and cannot be represented as financially posted.
Posting acceptance and its financial effects remain atomic. No background retry,
outbox or callback is introduced here; a future async design must preserve these
contracts under a separately approved ADR.

The following are capabilities to specify in the approved implementation package,
not new permission codes or grants in this session:

| Action | Required boundary |
| --- | --- |
| View, source drill-through, export | Active authorized membership, business permission and applicable object scope; linked evidence has its own read checks. Do not leak denied source details through journals/reports. |
| Prepare, approve, post, reverse | Distinct business permissions and approved maker/checker policy; workflow assignment alone does not grant authority. |
| Change rules/mappings, close/reopen | Explicit privileged business permission, reason, audit and approved separation; role labels or positions alone do not authorize. |

New capabilities require `BusinessPermissionCode`, registry entries, catalog/default
grant migrations and view/service enforcement with negative tests. No implicit
Tenant Owner, Tenant Admin, Platform Admin, Superuser or support exception is implemented here: D1/E1/revised F2 now
supply policy direction, while compatible implementation remains open. Suspended tenants cannot
mutate business data; cancelled tenants cannot use normal business access.

## 5. Reversal, close and reconciliation

Proposed period lifecycle is `open -> closed`; authorized `closed -> open` requires
reason and preserved close/reopen evidence. Posting and close must lock the same
period control so neither can validate stale state. Close evaluates in-scope
unposted/rejected sources, source/subledger/GL differences and unresolved material
exceptions. Materiality, exception signoff and the exact close checklist need
an accepted versioned policy/source basis; do not invent a tolerance or waive
mismatches here.

No backdated mutation of closed history. A late correction is blocked until an
authorized explicit reopening or an approved adjustment in an open period; exact
date policy remains open. Reversal retains original source/rule/amount lineage,
uses the approved correction date, and is itself idempotent. A replacement links
both the corrected source version and reversed journal. Reversing a settlement
reopens the obligation and cash allocation capacity; it does not by itself mean
the bank refunded money. A real refund is a distinct Treasury economic event.

| Reconciliation owner | Control and retained evidence |
| --- | --- |
| Source domain + Accounting | Every eligible event maps to its posting result or a named pending/rejected/excluded reason; compare event/line values and versions, detect omissions and duplicates. |
| AP/AR + Accounting | Opening balances + recognized obligations + signed adjustments - active settlements = outstanding; reconcile by tenant, currency, party and applicable dimensions/as-of date to GL control accounts. |
| Treasury + Accounting | Opening cash + receipts - disbursements plus explicit corrections matches cash-control GL; bank differences retain unmatched/in-transit/clearing evidence. A bank match cannot create a second movement. |
| Project Cost | Trace classified actuals to authoritative source/subledger/posting facts; exclude settlement-only cash as duplicate cost and keep legacy report meanings distinct. |

Each run needs scope, cutoff, source versions, counts/totals, exception identities,
owner and resolution evidence. Compare like currencies and periods; retain opening
and migration bridge lineage. Resolving an exception uses a source correction,
mapping repair with controlled reversal/replacement, or approved evidence-backed
disposition, never a direct balance edit. Detailed workbench delivery stays P10.2.

## 6. Payment containment and correction sequence

No existing model, field, migration, report or endpoint changes in S04. Future
transition follows expand -> map/backfill -> switch -> validate -> separately
approved contract/removal:

1. **Design prerequisites:** accept the detailed ADR, resolve affected Q01/Q02,
   complete Q04 accountable review and obtain package approval. P1.1 object scope and P1.2 settings/masters
   remain P2.1 prerequisites; terms/regulatory ownership stays with its own package.
2. **P2.1 expansion:** establish posting/period authority, controlled manual/opening
   sources and one explicitly selected pilot producer with reconciliation.
   Pilot choice is open; the examples below do not select Billing for implementation.
3. **P3.1/P3.2 mapping:** inventory each legacy Payment and dependent allocation/
   settlement by tenant and a controlled cutoff. Keep explicit old-to-new links,
   original UUIDs/numbers, amounts, statuses, actors, dates, reasons and audit chain.
   Map Payment only to validated Treasury cash evidence, contract allocation to
   contractual allocation, and claim settlement to an AP/AR allocation only when
   the claim obligation, party, currency and remaining capacity are established.
4. **Resolve gaps:** currency, bank account, posting date/period, opening balances,
   source version and counterpart accounts require evidence and review. Missing
   party or incomplete history enters an exception register; a placeholder historical
   reversal reason remains labeled as such. Do not turn demo/report totals into
   authoritative historical journals. Approve per-tenant opening-balance versus
   historical-replay policy and ensure the two cannot double count the same event.
5. **Switch and verify:** one writer owns each economic event. Reconcile old/new
   counts, amounts, outstanding and void/reversal effects by scope at cutover;
   preserve compatibility readers and drill-through. Legacy void paths must call
   the accepted integrated correction contract after mapping, so GL cannot be
   bypassed. Never dual-post from both old and new sources.
6. **Rollback and retention:** before financial cutover, rollback may disable new
   writes while retaining mapping evidence. After authoritative new postings,
   prefer controlled forward correction; rollback must not discard journals or
   reactivate a legacy writer without reconciled ownership. Rehearse restore and
   rollback under P0.2's approved recovery plan. Removal/rename, history reset and
   destructive migration still need separate explicit approval and Q03 retention
   review; they are not a consequence of completing P0-S04.

## 7. Illustrative posting and lineage walkthroughs

These are proposal-review examples in one hypothetical approved currency `C`,
using Decimal amounts, not certified accounting rules, an IRR decision, statutory
advice or executed tests. Tax, retention, advances and FX are intentionally absent;
their mappings still require versioned policy/source evidence. P3-S27-Q01/Q02 now
accept staged approved-claim AR semantics and the explicit directional event/role
contract, but do not authorize implementation or select actual Tenant accounts.
Account labels are roles, not an approved chart of accounts.

| Event | Illustrative balanced journal | Lineage and expected result |
| --- | --- | --- |
| Recognize approved claim version A for 100 | Dr AR control 100; Cr policy-selected recognition account 100 | Claim/version + recognition occurrence -> AR obligation -> journal; outstanding 100. Recognition timing/account still requires an accepted versioned policy before use. |
| Receive 60 before assigning it | Dr cash 60; Cr unapplied receipts 60 | Treasury movement/version -> cash journal, exactly once; AR outstanding remains 100. Contract allocation alone does not recognize another receipt. |
| Apply that 60 to claim A | Dr unapplied receipts 60; Cr AR control 60 | AP/AR allocation -> claim obligation + Treasury receipt + settlement journal; outstanding 40, cash still 60, unapplied balance 0. |
| Reverse that application | Dr AR control 60; Cr unapplied receipts 60 | Reversal links original allocation/journal and reason; outstanding 100, cash still 60, unapplied 60. Retry returns the same result. |
| Correct a receipt that never occurred | Dr unapplied receipts 60; Cr cash 60, after reversing dependent application above | Integrated correction retains original receipt and linked reversal; cash/unapplied 0, outstanding 100. A real refund needs a distinct movement instead. |
| Recognize payable 80, then pay/apply 30 | Recognition: Dr reviewed cost/asset 80, Cr AP 80. Movement: Dr outgoing clearing 30, Cr cash 30. Application: Dr AP 30, Cr outgoing clearing 30. | Supplier source/version -> AP item -> Treasury movement -> allocation, with separate event/journal identities; AP outstanding 50, cash decrease 30, clearing 0; cost/asset recognized only once. |

Under accepted P3-S27-Q02, the AR application debit is the exact
unapplied-receipt/settlement-clearing role created by the Treasury posting
contract, never the cash/bank account. AP application uses the equivalent exact
outgoing-clearing role. Subledgers never select or mutate Treasury cash-account
postings.

For every row: a repeated business event cannot create another journal; changed
payload with the same key is rejected. Closed-period posting, unknown currency,
cross-tenant party/source or disallowed project fails without partial financial
effects. Rule upgrades do not repost existing rows. These scenarios and the
arithmetic were reviewed statically; future integration tests must prove them.

## 8. Acceptance gates and consequences

The proposal improves source traceability and prevents competing financial
authorities, but adds explicit mapping, reconciliation and transactional coupling.
Historical gaps may block automatic migration; no claim of effortless backfill or
completed PPC-02 is made.

| Open input / owner | Required gate |
| --- | --- |
| Q01 / Product Owner and Platform policy owner | Product scope is recorded in section 9: IRR initial base/storage/display, multi-currency-ready but no FX behavior, UTC/ISO persistence with Jalali UI and explicit fiscal calendar, versioned precision categories and no current financial inventory valuation. Exact accounting precision/rounding facts require a configured, sourced policy before use. |
| Q02 / Product Owner and Platform policy owner | Export-only initial boundary and official-source hierarchy are recorded in section 9. Actual source versions are required where the policy declares provenance mandatory or the feature makes a source-backed regulated claim; professional evidence is optional governance metadata, not a global development gate. No current BillingPolicy rate is certified. |
| Q04 / Product Owner and security/workflow design owner | A1-B1-C1-D1-E1, revised F2, final G3 — Revised with Protected Operations, and H1 are selected. Named security/workflow/accounting and applicable legal review remains before affected acceptance. Protected Operations prohibit Self-Approval; financial/business approvals may be platform-configurable and, where permitted, tenant-configurable with full audit and tenant-specific control/regulatory responsibility. |
| Migration / Product Owner and operator | Select pilot, cutoff, replay/opening strategy, source-version bridge and reconciliation/rollback acceptance before P2/P3 rollout. Optional professional evidence may be attached to the exact reviewed version. |
| Q03 and D03-D05 / existing S03 owners | Retain original storage/retention, hosting, recovery and commercial gates. This proposal supplies no location, duration, RPO/RTO, quota or price. |

The complete [S03 open-input register](../ROADMAP_EXECUTION_PLAYBOOK.md#unresolved-parameters-and-latest-gates)
remains authoritative for unaffected inputs, including D01 pilot/workload details.
Section 9 supersedes the historical Q01/Q02 decision status in this table; actual
source/policy validation remains outstanding only for affected activation.

Before implementation acceptance, approved packages must test: tenant/project and
permission denials (including inactive/suspended/cancelled contexts); source and
dimension mismatch; Decimal balance/rounding; concurrent retries and same-key
changed-payload conflict; source revision/rule-upgrade duplication prevention; close/post
races; atomic audit/workflow/subledger failure; reversal/closed-period handling;
allocation caps; migration double counting and rollback; and source-to-subledger-
to-GL tie-out. Existing Payment/Billing behavior remains a regression obligation.
These are planned gates, not passing test results. P0/P0.1 and the final release
contract remain incomplete; accepting this ADR also would not authorize packages.

## 9. P1-S14 Product Owner disposition and incorporated Q01/Q02 baseline

The Product Owner's D14-01 instruction held acceptance pending until the recorded
Q01/Q02 decisions were incorporated. The following incorporation was checked
against sections 2-8 and introduces no contradiction, so D14-01 Option A now
accepts this ADR as target architecture only:

- one explicit Tenant base currency; initial support, canonical storage and all
  monetary display are IRR; no Toman denomination; multi-currency-ready design but
  no FX transaction, conversion, revaluation or exchange-rate accounting in scope;
  unsupported conversion fails closed;
- UTC timestamps and ISO/Gregorian-compatible persistence/processing, Jalali UI
  display, explicit Tenant fiscal-calendar configuration and effective-dated
  changes that never rewrite historical meaning;
- platform-governed, versioned domain precision policies distinguishing money,
  quantities, rates/percentages, intermediate results and document totals;
  a configured versioned policy with required provenance must supply any method,
  scale or rounding point before use;
- no authoritative financial inventory valuation in P1-S14/current Inventory;
- export/preparation only for the initial statutory boundary, not autonomous
  filing; official versioned sources are primary authority and reviewed
  professional interpretations may only supplement them; and
- Platform Admin owns the allowed versioned policy space; Tenant Owner selects and
  Tenant Admin applies permitted options. Professional review is optional evidence,
  not an application role or global development gate.

This disposition approves no Chart of Accounts, statutory rate, recognition rule,
filing, implementation, pilot, migration or release. The pending evidence remains
a blocking gate for P1-S14 implementation and every affected financial use.

## 10. P2-S05–S38 implementation conformance and handoff note (2026-09-30)

The approved P2 decision bundle has now implemented the bounded manual/opening
kernel described by this ADR. Accounting owns Tenant-scoped accounts, fiscal
periods, transactional journal numbering and immutable balanced journals. Posted
lines retain account and independent Project/Site/WBS/BusinessParty snapshots.
The code-owned registry accepts only manual, opening, reversal and replacement
contracts; journals pin source UUID/version, event/occurrence identity, canonical
payload hash and posting-rule version under database uniqueness.

Posted corrections use one linked reversal and, when required, a linked
replacement. Reviewable opening imports retain cutoff, source evidence and
reconciliation references and produce one opening journal without historical
replay. Protected posting, reversal, opening acceptance and period controls retain
permission, reason, audit and independent membership evidence. PostgreSQL
constraints and tests cover fiscal overlap, duplicate/concurrent posting, closed
periods, Tenant/permission separation and opening/reversal behavior.

This note records implementation conformance only. It does not approve an
operational producer, Treasury/AP/AR, FX, tax, filing, valuation, background jobs
or any currently unset precision/rounding value; all continue to fail closed or
remain outside this package.

P2-S13 closes the source-line identity gap inside the accepted boundary. The
registry describes the Accounting owner and constrained source/source-line models,
and journal lines pin a durable UUID back to the manual line itself, the exact
opening-import line or the reversed journal line as applicable. The new
Tenant-scoped synchronous preflight compares accepted opening facts to the posted
journal at line and dimension level, reports pending sources and named exceptions,
and totals only posted journals through the requested cutoff. It is a read-only
diagnostic, not retained reconciliation evidence or approval. No operational
source adapter or producer contract was added.

P2-S14–S15 retain each manual/opening/correction result as an immutable
Tenant-scoped run with a versioned scope and cutoff, deterministic scope/input/
result hashes, exact counts/totals, creator membership and ordered immutable
exception snapshots. Identical input retries return the existing run and do not
duplicate its audit event. At that checkpoint this evidence was not an exception
disposition, review or protected sign-off; those controls were gated to P2-S18–S19.

P2-S16–S17 make the retained result inspectable at the source boundary. Scope
version 2 stores ordered immutable tie-out snapshots for every bounded manual,
opening and correction fact. The snapshots retain source/journal line counts,
debit and credit totals, source version, exact line/account/amount evidence,
dimension identifiers and posted dimension snapshots. Accepted opening imports
must match their exact posted lines; reversal chains must invert the linked source
amounts while preserving line and dimension lineage; replacement chains pin the
linked source and next version while permitting corrected line and amount shape.
The run result hash covers this evidence. Pending opening inputs remain explicit
pending facts rather than fabricated failures. That S16–S17 slice introduced no
exception disposition, review, sign-off or producer behavior.

P2-S18 adds one append-only disposition per retained exception. The bounded
catalogue distinguishes correction required, explained variance and not applicable;
each action requires a dedicated Tenant permission, non-empty reason, actor
membership and audit event, with an optional evidence reference. Exact retries are
idempotent and conflicting second dispositions fail closed. The disposition is a
classification record only: it cannot rewrite the immutable run, exception,
tie-out, journal or balance and it is not approval or sign-off. Protected
independent review and separation of duties remain P2-S19.

P2-S19 adds one protected independent review per retained run. The sign-off service
requires its own permission and non-empty reason, locks and re-reads the run, verifies
the scope/result hashes, ordered exception/tie-out evidence and original creation
audit, requires every exception to have an immutable disposition, and pins the run,
disposition and combined evidence hashes. The signer cannot be the run creator or
any disposer for that run. Exact retries return the same review; conflicts and
tampering fail closed. P2-S20–S21 verify these rules, Tenant isolation, cutoff
stability and concurrent idempotency on PostgreSQL. Sign-off never edits a
disposition, retained snapshot, journal or balance. P2-S22 selects no operational
producer; that requires a separate complete producer contract and Product Owner
approval.

P2-S28–S34 add no producer. Trial balance, balance sheet, profit/loss and account
ledger drill-through are derived solely from posted immutable journal lines and
their retained account/dimension snapshots. Retained statement runs pin scope,
input, result and exact source-line evidence and are append-only. Period close
requires no draft/proposed journals or pending opening imports, a cutoff-matched
independently signed reconciliation, and retained trial-balance/balance-sheet/
profit-loss evidence; close and reopen create separate immutable hash-pinned events,
and the reopen actor/requester remain independent from the close approver. A late
controlled adjustment is a new manual journal linked to the posted source journal,
requires reason and evidence references, and is permitted only in an explicit open
adjustment period. It never mutates closed journals, lines, reconciliation evidence,
statements or prior close history.

P2-S35–S37 serialize every affected financial mutation on the Tenant row before
narrower Accounting locks. This gives posting and journal-number allocation,
retained statements, reconciliation/disposition/sign-off, period controls and
correction paths one deterministic contention boundary. Close re-verifies the
signed reconciliation against current cutoff evidence while holding that boundary,
then validates retained statement headers and exact line snapshots before reuse.
Exact retries return the existing posting, statement, close/reopen event, reversal
or controlled adjustment; conflicting requests fail closed. Focused PostgreSQL
regression covers the contention and stale-cutoff cases, and migration `0009` has
been rehearsed backward to `0008` and forward again without adding schema.
