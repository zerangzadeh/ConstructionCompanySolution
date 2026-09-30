# P2-S38 P3 Handoff Packet

**Status:** P2-S38 complete on 2026-09-30. This packet records the completed P2
session boundary; it is not authorization to begin P3.

## 1. Delivered P2 boundary

Accounting is the sole general-ledger authority. The delivered bounded surface is
Tenant-scoped and synchronous: chart of accounts, fiscal years/periods, manual and
reviewable opening journals, immutable posted lines and retained account/dimension
snapshots, source/event identity, idempotency, reversal/replacement, retained
reconciliation/tie-out/disposition/sign-off evidence, retained financial statements,
append-only close/reopen history and linked controlled adjustments in explicit open
adjustment periods.

Financial reporting and evidence use only posted immutable journal lines, their
retained snapshots, retained statement runs, reconciliation evidence and
append-only period-control history. Draft/proposed records, legacy financial read
models and operational-domain records are not financial authority.

## 2. Non-negotiable invariants for P3 consumers

- Treasury owns cash movements, instruments and bank evidence; AP/AR owns
  obligations, open items and settlements; neither may create a competing ledger.
- Any future producer submits a registered, versioned and balanced Accounting
  proposal. Accounting alone validates Tenant scope, authorization, open period,
  dimensions, policy/rule versions, idempotency and posting.
- Finalized journals, lines, retained statements, reconciliation evidence,
  dispositions, reviews and close/reopen events are immutable. Correction uses only
  linked reversal, replacement or controlled adjustment; no direct rewrite,
  delete, repost or dual-post path is allowed.
- Financial mutations serialize at the Tenant Accounting boundary. Retried work
  must return the existing result or fail closed; it must not allocate another
  journal number or create duplicate evidence.
- Close requires no unresolved draft/proposed journal or opening import, current
  cutoff-matched independently signed reconciliation and retained statements.
  Reopen remains a separately authorized, independently evidenced operation.

## 3. Verified handoff evidence

- `47 passed` in the focused PostgreSQL Accounting regression suite, covering
  tenant scope, permissions, SoD, CSRF/UI boundaries, retries, contention,
  duplicate posting/numbering, retained statements, stale cutoff, close/reopen,
  corrections and immutability detection.
- Accounting migration `0009` was rehearsed from `0008` backward and then forward
  on PostgreSQL. No P2-S35–S38 migration or dependency was added.
- Django system checks, migration-drift check and Ruff passed. The authoritative
  session disposition is in [ROADMAP.md](../../ROADMAP.md) and the execution
  record is in [the P2 session map](../ROADMAP_EXECUTION_PLAYBOOK.md#8-p2-session-map--38-sessions).

## 4. P3 entry gates

Product Owner approval is required before P3 work begins. The approved work package
must name the first P3 capability and, before any operational posting, identify the
producer and owner; finalized-source eligibility; source/version/line identity;
recognition and mapping policy; precision and currency basis; idempotency and
atomicity; correction/close/cutoff behavior; reconciliation exceptions; Tenant,
object-scope, permission and SoD controls; rollout, migration, recovery and
rollback evidence.

P3.1 additionally needs party bank-profile and object-scope decisions and an
explicit decision for any statement/import asynchronous work. Current `Payment`
and `PaymentAllocation` require a controlled semantic inventory and
expand/map/backfill/switch/validate plan; they are not Treasury, AP/AR or journal
authority. Do not synthesize journals from legacy totals or activate a legacy writer
after cutover without reconciled ownership.

Professional/statutory review, configured precision/rounding values where a
financial operation activates them, production migration/recovery acceptance and
all existing security/operations gates remain open. Controlled export is also
separately planned and unapproved.

## 5. Explicit exclusions retained after P2

No operational producer, Treasury, AP/AR, cash/bank account or reconciliation,
cheque, payroll, export, background job, new dependency or P3 implementation was
delivered by P2. P3 must start from the current code, migrations and focused tests,
not from a presumed operational financial history.
