# P3-S18–S22 Statement Import and Bank Reconciliation Implementation Contract

**Status:** accepted implementation contract — authorized by the Product Owner on
2026-10-01. This contract is the application-change boundary for P3-S18–S22.

## 1. Scope and session allocation

| Session | Authorized outcome |
| --- | --- |
| P3-S18 | Expand-only statement-import, row-evidence, permission and audit foundation. |
| P3-S19 | Synchronous preview/accept services with exact source and row duplicate controls. |
| P3-S20 | Exact deterministic match selection and retained ambiguous suggestions. |
| P3-S21 | Authorized match confirmation, bank clearing and forward correction/reversal. |
| P3-S22 | Immutable bank-reconciliation evidence, focused PostgreSQL acceptance and documentation closeout. |

Legacy `Payment` cutover/backfill, production activation, AP/AR, UI, background
processing, external bank integration, P3-S23+, and `MATERIAL_DOCUMENTS_LINK` are
out of scope. No file parser, provider adapter, credential, network callback,
queue, scheduler, tolerance, score, threshold, financial rule, or numeric default
is introduced.

## 2. Ownership and lifecycle

Treasury owns statement imports, retained bank rows, match evidence, clearing and
bank-reconciliation evidence. Accounting continues to own journals and fiscal
books. A statement row is external evidence, not a Treasury movement or journal;
a match or clearing never creates a second cash movement or Accounting entry.

An import is `previewed`, `accepted`, or `cancelled`. Preview validates and stores
the exact file hash, file size, provider/account/period identity, canonical row
facts and exact row evidence. Accepted and cancelled imports, and every row of an
accepted import, are immutable. Only a preview may be accepted or cancelled.
Cancellation is permitted only before acceptance and retains the preview.

A match proposal is immutable evidence with one statement row, one posted
Treasury movement and its account leg, a basis and whether the proposal was the
unique deterministic result. It may be `suggested`, `confirmed`, `rejected`, or
`reversed`. Confirmation creates one active clearing. Rejection creates no
clearing. Correction never edits or deletes accepted evidence: it appends a
clearing reversal and moves the proposal to `reversed`; a later proposal is new
evidence.

## 3. Import validation, bounds, duplicates and idempotency

The synchronous application service receives opaque source bytes plus canonical
rows. The bytes are retained only as a SHA-256 identity; storage of the bank file
itself and upload handling remain outside this package. Each row retains its
provider row identity when present, normalized financial facts, an exact
SHA-256 evidence hash, and a non-sensitive raw-evidence JSON object supplied by
the future approved adapter. Secrets and unmasked account identifiers are
forbidden in that object.

Because D3-11 deliberately leaves formats and numeric limits open, the service
has no default format or limit. Its caller must supply positive `max_file_bytes`
and `max_rows` for the invocation; the service records and enforces those exact
bounds and fails closed when either is absent, invalid or exceeded. This provides
bounded synchronous execution without selecting a Product Owner value. No
production caller is authorized until those values and a provider adapter are
separately approved.

Validation requires a Tenant-owned active bank account; non-empty provider and
format identifiers; an ordered, non-empty finite row collection; inclusive
statement dates; IRR currency; positive `Decimal` amounts; valid direction and
dates within the declared period; unique positive row numbers; and consistent
Tenant/account relationships. The service does not infer missing dates,
directions, amounts, references, provider identities, or rows from free text.

The exact file duplicate key is Tenant + Treasury account + SHA-256 file hash.
The exact row duplicate key is Tenant + Treasury account + row evidence hash.
Provider row identity, when supplied, is additionally unique for Tenant + account
+ provider. A duplicate preview with the same idempotency key and payload returns
the original aggregate; reuse with a different payload fails. A different key
for an already imported file or row fails. Acceptance is idempotent for the same
actor/reason payload and otherwise fails once the import has left preview.
Database constraints remain the final concurrent duplicate barrier.

## 4. Permissions and object scope

The package adds and registers dedicated permissions:

- `treasury.statements_import` — preview and cancel imports;
- `treasury.statements_accept` — independently accept a validated preview;
- `treasury.statement_matches_manage` — generate, reject and reverse match evidence;
- `treasury.statement_matches_clear` — confirm a match and create clearing;
- `treasury.bank_reconciliations_run` — retain a bank reconciliation run.

Every service resolves an active membership, active Tenant, permission and exact
Tenant ownership. Import and reconciliation are bank-account scoped. Movement
project/site scope is rechecked when a match is proposed or confirmed through
the existing authorization service; a bank statement never widens object scope.
Identifiers supplied by callers are re-read under the locked Tenant.

Default role grants remain deny-by-default: `ACCOUNTANT` receives these finance
permissions; `OWNER` and `ADMIN` continue to receive the platform's unrestricted
Tenant role grants; other default roles receive none. Sensitive identifiers are
not added to statement evidence or audit metadata.

## 5. Audit, SoD and Self-Approval

Audit events retain import preview/accept/cancel, proposal generation/decision,
clearing reversal and reconciliation execution with organization, actor, object,
reason where applicable, exact hashes and non-sensitive result counts.

Preview maker and import accepter are subject to D3-09. Match proposer and
confirmer are also subject to D3-09. The accepted, versioned Treasury
Self-Approval policy is resolved and pinned at acceptance/confirmation: the same
membership may act only when that policy explicitly permits it; otherwise an
independent permissioned checker is mandatory. Reconciliation is evidence
generation, not approval. P3-S30–S31 independent exception disposition/sign-off
remain out of scope. No Protected Accounting Operation is performed here and no
Treasury policy may authorize journal posting, reversal, or period override.

## 6. Lock order and concurrency

All mutations are atomic and use the established coordination order:

1. `Organization` coordination row;
2. active actor/checker membership rows in UUID order;
3. `TreasuryAccount` rows in UUID order;
4. statement import, then statement rows in row-number/UUID order;
5. `TreasuryMovement` rows in UUID order, then movement legs;
6. match proposal, then active clearing/reversal evidence.

No service locks Accounting rows. Database uniqueness constraints arbitrate
concurrent file, row, provider-row, proposal, and active-clearing attempts. A
losing transaction returns the existing same-payload result only for the explicit
idempotency contract; otherwise it fails without partial evidence.

## 7. Deterministic and suggested matching

Candidate direction must equal the movement leg cash direction; currency,
amount, bank account and transaction/movement date must match exactly; the
movement must be posted, not reversed, and not actively cleared. There is no
date window, rounding, amount tolerance, text similarity, confidence score or
learned rule.

Exactly one candidate produces a deterministic suggestion. More than one exact
candidate produces separate non-deterministic suggestions so an authorized human
can choose; zero candidates produces no proposal. Generation is idempotent and
requires an explicit key; reuse with the same candidate evidence returns the
original proposals and reuse with changed evidence fails. A new key after a
rejection or reversal appends a new proposal attempt. Generation does not clear
anything. Confirmation re-runs every exact invariant under locks
and requires that no other active clearing exists for either row or movement.

## 8. Clearing, cheque boundary and correction

Confirmed matching creates immutable `TreasuryMovementClearing` evidence. It
changes neither movement status nor Accounting history. Existing cheque
cash-on-confirmed-clearing remains authoritative: a cheque must first be cleared
through the existing `clear_cheque` service, which creates/posts its movement;
the resulting posted movement may then match the bank row. Statement matching
does not silently transition a cheque or synthesize a movement.

Reversal requires an explicit reason, the manage permission and an active
clearing. It appends one immutable reversal, deactivates only the derived current
match state through the service, and leaves the statement row, movement, journal,
cheque and prior evidence intact. Reversing a Treasury movement remains the
existing protected integrated Treasury/Accounting operation; clearing reversal
does not reverse cash or the journal.

## 9. Treasury/Accounting boundary and reconciliation

Bank reconciliation is an immutable as-of snapshot for one accepted statement
import/account. It records statement in/out totals, actively cleared book in/out
totals, counts, exact unmatched row and uncleared posted-movement identifiers,
exceptions and an evidence hash. Exact equality is used; no tolerance is
selected. The run is read-only evidence and cannot post, adjust, dispose, sign
off, reopen a period, or mutate a source. Treasury-to-GL reconciliation remains
the existing separate control; together they preserve bank -> Treasury movement
-> Accounting journal drill-through without merging authorities.

## 10. Migration, rollback and focused acceptance evidence

Schema changes are expand-only: new Treasury evidence tables and lifecycle
constraints, new permission catalog entries/default grants, and new audit-action
choices. There is no data migration, legacy backfill, writer cutover or Tenant
activation. Before authoritative production use, a later gate must approve the
provider adapter, exact file formats, byte/row limits, storage/retention policy,
pilot Tenant/cutoff, tolerances (if any), recovery operator and go/no-go reviewers.

Pre-activation rollback may reverse the expand-only migrations after dependency
checks. Once accepted evidence exists, rollback is forward-only: disable the
caller, retain evidence, and correct through clearing reversal; never delete or
rewrite financial history.

Focused PostgreSQL acceptance must cover Tenant/object scope; permissions;
policy-controlled Self-Approval; invalid/unbounded/duplicate file and row
rejection; idempotency-key conflict; exact deterministic versus ambiguous
suggestions; concurrent duplicate acceptance/clearing; immutable correction;
bank reconciliation totals/hash; and Treasury/Accounting non-mutation. Complete
`makemigrations --check`, Treasury migration rollback/reapply, Django checks and
targeted Ruff. Broader unrelated known failures remain outside this tranche.

## 11. Explicit deferred Product Owner decisions

The following values are not required by the dormant service/model foundation
and are intentionally not invented: provider and bank file formats; approved
file source; byte and row limits; raw-file storage and retention; any date/amount
tolerance, confidence threshold or numeric approval threshold; live connectivity;
pilot Tenant/cutoff; production recovery operators; and reconciliation sign-off
rules. The exact decision needed before a production caller is added is: name an
approved provider/format adapter and its positive maximum file bytes and row
count, plus the approved source-file retention/storage policy.

## 12. Implementation closeout

The contract was finalized before application changes. The completed expand-only
implementation is `treasury.0005`–`0006`, `organizations.0061`, and
`audit.0043`, with format-neutral services in the existing Treasury authority.
It adds no parser, upload/UI route, background worker, bank connection, Accounting
producer, legacy data operation or production caller.

PostgreSQL acceptance passed four focused statement tests covering explicit
bounds, permissions, file/provider-row/exact-row duplicates, idempotency, retained
hash tamper detection, policy-controlled SoD, deterministic versus ambiguous exact
matching, concurrent single-effect acceptance/clearing, immutable correction,
bank reconciliation and Accounting non-mutation. The `treasury.0005`–`0006`
rollback/reapply rehearsal and three retained Accounting posting/reversal/
reconciliation regressions also passed. Django system and migration-drift checks
and targeted Ruff passed. Two focused permission-registry checks and eleven
role-default subtests passed; two broader registry checks retain only the
pre-existing namespace and `MATERIAL_DOCUMENTS_LINK` gaps.

No unresolved Product Owner value was required by this dormant boundary.
Production invocation remains blocked until the exact provider/format adapter,
positive file-byte and row limits, and source-file storage/retention policy are
approved. P3-S23+ remains unauthorized.
