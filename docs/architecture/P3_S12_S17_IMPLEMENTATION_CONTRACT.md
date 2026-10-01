# P3-S12–S17 Payment Request and Advance Implementation Contract

**Status:** COMPLETE WITH EXPLICIT DEFERRALS  
**Authorization date:** 2026-10-01  
**Authority:** Product Owner authorization for P3-S12–S17, constrained by the
current ROADMAP, Execution Playbook, accepted D3 decision packet, and existing
authorization, Accounting, and Treasury contracts.

## 1. Scope and session allocation

This contract is the required pre-implementation gate for P3-S12–S17. It adds no
AP/AR authority and does not change the accepted legacy `Payment` transition.

| Session | Bounded implementation outcome |
| --- | --- |
| P3-S12 | Tenant-owned, unscheduled payment-request aggregate with employee or BusinessParty beneficiary and immutable monetary/context identity. |
| P3-S13 | Request submit/approve/reject/cancel/release services, dedicated permissions, effective Self-Approval policy evidence, audit, Tenant/object validation, and exact linkage to one posted disbursement. |
| P3-S14 | **DEFERRED:** payment scheduling, due-date calculation, payment proposals/batches, prioritization, liquidity rules, and every date/amount threshold. No schema or default is introduced. |
| P3-S15 | Employee/vendor advance aggregate opened only from an approved and released advance request whose exact posted disbursement is retained. |
| P3-S16 | Cash-return advance-settlement lifecycle and integrated append-only reversal. Non-cash expense/invoice substantiation is excluded until its owning producer and Accounting mapping are authorized. |
| P3-S17 | Immutable advance-to-Treasury-to-GL reconciliation runs, focused PostgreSQL acceptance tests, and documentation closeout. |

The tranche stops at these outcomes. Statement import/matching/reconciliation,
AP/AR, legacy cutover/backfill or semantic remapping, pilot/cutoff/production
activation, external bank integration, UI, background work, and P3-S18+ remain
outside authorization. `MATERIAL_DOCUMENTS_LINK` remains an independent known
issue.

## 2. Ownership and lifecycle

Treasury owns payment requests as cash-execution proposals, advances as
operational cash-custody balances, settlement applications, and their retained
reconciliation evidence. Workforce continues to own `Employee`; Parties continues
to own `BusinessParty`; Accounting alone owns journals, accounts, fiscal periods,
and posted balances.

### 2.1 Payment request

- Identity: Tenant, UUID, idempotency key/payload hash, request kind, beneficiary,
  positive IRR amount, purpose, optional same-Tenant project/site, creator, and
  timestamps.
- Kinds are platform-closed: ordinary payment, employee advance, and vendor
  advance. Exactly one beneficiary is required: employee for employee advances;
  BusinessParty for ordinary/vendor requests. No due date or schedule field is
  created.
- Lifecycle: `draft -> submitted -> approved -> released`; `submitted ->
  rejected`; `draft|submitted|approved -> cancelled` only before release.
- Release links exactly one approved request to exactly one already-posted,
  unreversed Treasury disbursement for the same Tenant, amount, currency and
  beneficiary context. Release neither creates a second cash fact nor posts a
  journal.
- Submitted and later request content is immutable. Rejected/cancelled requests
  are terminal. Released requests are corrected through the linked movement and
  advance correction services, never by status rewind or amount edit.

### 2.2 Advance and settlement

- An advance is opened exactly once from a released employee/vendor-advance
  request and pins the request and its posted issue movement. It does not create a
  journal or duplicate cash.
- Advance lifecycle is derived and service-controlled: `open`,
  `partially_settled`, `settled`, or `reversed`. Approved active settlement
  applications reduce the outstanding amount; they cannot make it negative.
- A P3-S16 settlement is a cash-return application only. It references one posted,
  unreversed Treasury receipt with the same Tenant and beneficiary context.
  Lifecycle is `draft -> submitted -> approved`; `submitted -> rejected`; or
  `draft|submitted -> cancelled`. Only approved applications affect outstanding
  balance.
- One receipt may support multiple advances only up to its posted amount. One
  advance may have multiple applications only up to its issued amount. These are
  conservation invariants, not configurable thresholds.
- Non-cash employee expense reports, supplier invoices/credits, write-offs,
  payroll deductions, claim recovery, and AP/AR allocation do not settle an
  advance in this tranche.

## 3. Permissions and object scope

The following dedicated `BusinessPermissionCode` values are added and registered:

- `treasury.payment_requests_create`
- `treasury.payment_requests_submit`
- `treasury.payment_requests_approve`
- `treasury.payment_requests_release`
- `treasury.advances_manage`
- `treasury.advances_settle`
- `treasury.advances_reverse`

`treasury.view` remains the read permission and
`treasury.reconciliations_run` governs retained advance reconciliation. Default
grants follow the existing restricted Treasury posture: Tenant Owner, Tenant
Admin, legacy Company Owner compatibility role, and Accountant receive the new
permissions; Manager, Supervisor, and Viewer do not. Possession of a role label,
workforce position, project assignment, legacy Payment permission, or UI
visibility grants nothing independently.

Every service resolves the actor through active membership in the supplied
organization, requires an active Tenant, checks the operation permission, and
validates all related records share that Tenant. Optional project/site references
are classification scope: site must belong to project and the actor's current
project/site grants must permit the context. Such scope never grants access to a
Treasury account or another beneficiary. Cross-Tenant IDs fail closed.

## 4. Authorization, SoD, and Self-Approval

Payment-request approval and advance-settlement approval are Treasury business
operations governed by the accepted, effective, scope-bound
`treasury-self-approval` Platform/Tenant policy. The locked transaction pins the
effective policy version:

- if `allow_self_approval` is `true`, the same permissioned active membership may
  submit and approve;
- if it is `false`, approver and maker must be different active memberships;
- missing, inactive, ineffective, malformed, or wrong-consumer policy fails
  closed;
- no numeric threshold or additional-approval rule is evaluated because none is
  accepted for this tranche.

Request release consumes an already posted movement and cannot bypass the
movement's approval and protected Accounting post. Advance issue reversal and
settlement reversal call the existing posted-movement reversal boundary, where
Accounting journal reversal is a Protected Operation and therefore always
requires an independent requester/checker regardless of the Treasury
Self-Approval setting.

## 5. Audit events and retained evidence

Append-only audit actions are added for request creation/transition/release,
advance opening/reversal, settlement creation/transition/reversal, and retained
advance reconciliation. Metadata contains only UUIDs, lifecycle states, policy
version, reason, and non-sensitive totals/counts; it must not expose account or
beneficiary sensitive values.

Domain transition rows retain organization, aggregate, from/to state, actor,
maker where approval is involved, effective approval-policy version, reason, and
time. Release/opening evidence retains exact request/movement identity. Settlement
and reversal evidence retains original/reversing movement and application links.

## 6. Lock order and concurrency

All mutations use `transaction.atomic()` and this global order:

1. `Organization` financial coordination row;
2. payment request, then advance, then settlement aggregate when applicable;
3. Treasury movements in UUID order;
4. related application rows;
5. Accounting service locks under its existing fiscal-period/journal order.

Approval re-reads state, membership, permission, scope, policy, and maker/checker
inside the transaction. Organization-scoped uniqueness plus row locks prevent
duplicate request/release/opening/settlement/reversal outcomes and lost caps under
concurrent settlement.

## 7. Idempotency

Request creation and settlement creation use organization-scoped idempotency keys
and canonical payload hashes. Same key plus same payload returns the existing
aggregate; same key plus conflicting payload fails closed. Release and advance
opening are one-to-one and return the existing result only when every identity is
identical. Reversal is one linked result per original. Reconciliation uses an
organization-scoped run key and evidence hash; conflicting reuse fails closed.

## 8. Correction and reversal

Drafts may be deleted only before submission where existing retention rules allow;
submitted/final evidence is retained. Approved but unreleased requests may be
cancelled with reason. A released request is never reopened.

An issue movement linked to an advance cannot be reversed through the generic
movement service. The integrated advance-reversal service requires no active
settlement effect, creates the linked Treasury/Accounting reversal once, marks
the advance reversed, and retains audit evidence. A receipt movement with an
active approved settlement likewise cannot be reversed generically. Settlement
correction first creates append-only allocation-reversal evidence and recalculates
advance status. When that settlement is the receipt's sole exact allocation, the
same service also creates the linked protected cash/journal reversal. A shared or
partially unallocated receipt remains posted after one allocation is reversed; it
may be cash-reversed only after every active allocation is reversed. A settled
advance may therefore return to open/partial only through retained reversal
evidence, never status rewind.

## 9. Accounting/Treasury boundary and reconciliation

Requests, advances, and settlement applications are not journals or AP/AR open
items. Issue and cash-return amounts reach Accounting only through the existing
posted Treasury movements and `treasury.movement.posted.v1` evidence. P3-S12–S17
does not register another posting producer, select arbitrary ledger accounts, or
change precision/rounding policy.

The retained advance reconciliation verifies, per Tenant and cutoff:

- each non-reversed advance has one released request, one posted issue
  disbursement, one Treasury posting-evidence row, and one posted journal;
- each active approved settlement has one posted receipt, posting evidence, and
  posted journal;
- issue totals, active settlement totals, and derived outstanding totals conserve
  exactly; and
- missing/reversed/mismatched links are named exceptions, never silently netted.

This is advance-to-Treasury-to-GL source reconciliation only. It is not bank
statement reconciliation, period-close sign-off, AP/AR reconciliation, or legacy
Payment reconciliation.

## 10. Migration, rollback, and acceptance evidence

Migration is expand-only: new Treasury tables, constraints/indexes, permission
catalog/default grants, and audit choices. There is no data migration from
`Payment`, no backfill, no consumer switch, no semantic remapping, and no
production activation. Existing S05–S11 data and behavior remain authoritative.

Before authoritative use, rollback may stop new request/advance services and roll
back schema only when no retained records exist. After any request/advance or
settlement evidence exists, recovery is forward correction; migrations must not
delete financial history or reactivate a legacy writer.

Focused PostgreSQL acceptance must cover:

1. Tenant isolation, active membership, permissions, and project/site relation
   validation;
2. policy-controlled Self-Approval and independent checker when disabled;
3. absence of schedule/threshold defaults and fail-closed policy behavior;
4. create/submit/approve/release idempotency and conflicting-payload rejection;
5. employee/vendor beneficiary and exact posted-disbursement linkage;
6. concurrent settlement caps across one advance and one receipt;
7. protected integrated issue/settlement reversal with immutable lineage;
8. advance-to-movement-to-journal reconciliation and named exceptions;
9. migration/catalog/permission-registry consistency; and
10. focused S05–S11 Treasury and retained Accounting regressions.

Acceptance evidence is the migrations, focused PostgreSQL test results, Django
system/migration checks, targeted Ruff result, and reconciled ROADMAP/playbook/
architecture status. No pilot, cutoff, or production readiness is implied.

## 11. Explicit deferred Product Owner decisions

No current implementation step requires these values, so they do not block the
bounded work above. They remain exact future gates:

- **Scheduling:** select the owner and semantics for requested/due/execution dates,
  calendars, prioritization, payment proposals/batches, liquidity checks,
  rescheduling, expiry, and release timing.
- **Thresholds:** select versioned kind/account/amount bands, additional approval
  counts/routing, currencies/bases, effective dates, and behavior at equality.
- **Non-cash advance settlement:** authorize the owning expense, payroll, AP or
  other source aggregate; its approval/correction lifecycle; the registered
  Accounting producer/mapping; evidence eligibility; partial/rejected treatment;
  and source-to-advance-to-GL reconciliation.
- **Production activation:** separately supply the pilot Tenant, cutoff,
  opening-versus-replay coverage, tolerances, restore point, operators, and
  go/no-go reviewers required by D3-12.

## 12. Implementation closeout

The contract was finalized before application changes. The completed expand-only
implementation is `treasury.0004`, `organizations.0060`, and `audit.0042`, with
models/services in the existing Treasury authority and no new Accounting producer.

Acceptance evidence on PostgreSQL:

- all nine focused Treasury tests passed, including policy-controlled
  Self-Approval, exact request/movement linkage, cash-return cap conservation,
  protected reversal, retained reconciliation, and concurrent cap enforcement;
- three retained Accounting posting/reversal/reconciliation regressions passed;
- four focused permission/catalog tests and eleven role-default subtests passed;
- Django system and migration-state checks and targeted Ruff passed.

The broader permission-registry audit retains its independently pre-existing
managed-model/namespace gaps, including `MATERIAL_DOCUMENTS_LINK`; P3-S12–S17 did
not modify or absorb them. No deferred Product Owner value was required by the
implemented boundary, and no S18+ or activation gate was crossed.

