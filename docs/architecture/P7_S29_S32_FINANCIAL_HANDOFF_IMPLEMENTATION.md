# P7-S29–S32 Payroll Financial-Handoff Implementation Packet

**Status:** **Product Owner accepted (2026-10-04).** P7-S33–S36 is subsequently
Product Owner accepted, consolidating P7-S01–S36 as complete within documented
non-production boundaries; production activation remains unauthorized and P8 is
planning-only.

## Acceptance boundary

Product Owner acceptance covers only the proposal-only financial handoff
boundary documented here: finalized-Payroll liability, Accounting-source,
Treasury-payment and Project Cost distribution proposals; immutable source and
monetary-policy lineage; correction/reversal/replacement history; idempotency,
reconciliation and double-counting-risk evidence; separate prepare/review
permissions; and Persian-first RTL operations. AP/Subledger retains recognized
obligations/settlements, Accounting retains journals/GL, Treasury retains
payments/bank/cash/settlement, and Project Controls retains Project Cost actuals.
No automatic downstream recognition/execution, cross-domain approval, live filing,
provider integration, notifications, schedulers/queues or production activation is
authorized.

## 1. Bounded outcome

Payroll now publishes four immutable proposal families from finalized Payroll
facts: liability/AP-like source, Accounting source, Treasury payment source and
Project Cost labor distribution. A proposal is evidence, not a recognized or
executed downstream record. This tranche adds no AP/subledger obligation,
journal/GL entry, Treasury movement, bank-account choice, released payment, cash
movement or Project Cost actual.

## 2. Source and monetary contract

`FinancialHandoffProposal` pins the Tenant, finalized run/period, run calculation
digest, finalized employee-result amounts, currency, precision-policy version,
rounding-policy version and complete monetary-policy snapshot. Services re-read
and lock the run, require every result to be finalized, validate the pinned policy
snapshot, and copy authoritative amounts; they do not rerun Payroll calculation.
Stable `(organization, family, idempotency_key)` and `(organization, family,
run)` constraints protect retries and duplicates.

## 3. Family boundaries

- Liability proposals contain employee net payables and accepted finalized
  statutory employee/employer components. Missing statutory payee authority is
  explicit and prevents acceptance. AP/Subledger alone recognizes obligations.
- Accounting proposals preserve result-line/component lineage and accept a
  proposed accounting date or mapping reference only when supplied explicitly.
  Missing mapping is an exception. No account, debit/credit, period, dimension,
  journal, posting or reversal is invented.
- Payment proposals preserve employee/payee reference, amount, currency and
  Payroll lineage. Until payment authority is configured they remain fail-closed.
  No bank account, instrument, release, execution or settlement is selected.
- Project Cost proposals allocate `gross_amount + employer_amount`, both finalized
  Payroll facts, only across the matching approved timesheet's immutable entries.
  The run's pinned precision/rounding snapshot governs proportional allocation;
  the final line absorbs the exact remainder. Missing or inconsistent time remains
  an explicit unallocated line. Project Controls alone recognizes actual cost.

## 4. Correction, reversal and replacement

Original proposals have no predecessor. Correction, reversal and replacement
runs must find the same-family proposal for their explicit Payroll predecessor,
and the new immutable proposal links to it. Prior proposals, acknowledgments and
downstream records are never rewritten. Missing predecessor evidence fails
closed.

## 5. Review, acknowledgment and reconciliation

Review evidence is immutable and cannot accept a proposal carrying exceptions.
Downstream acknowledgment is Payroll-held evidence only. Reconciliation creates
no balance and performs no repair; it reports missing acknowledgment, duplicate
proposal, stale source, source/result mismatch, lineage mismatch, amount mismatch,
allocation mismatch and cross-proposal timesheet-entry double-counting risk.
Reconciliation review is separate immutable evidence.

## 6. Permissions and UI

Ten new default-denied permissions independently control prepare/review for each
of the four proposal families and prepare/review for reconciliation. Multiple
permissions may be granted to one user; this tranche introduces no person-level
separation beyond accepted downstream protected operations. The Persian-first RTL
workbench exposes proposals, minimum employee reference, exceptions, policy/source
evidence, correction lineage, allocation coding and reconciliation history.

## 7. Schema and implementation artifacts

- Payroll migration `0005_financialhandoffproposal_financialhandoffline_and_more`
  adds proposal, line, review, acknowledgment, reconciliation and reconciliation-
  review records plus database idempotency constraints.
- Organizations migration `0094_p7_s29_s32_payroll_handoff_permissions` registers
  the ten permissions without default grants.
- `apps/payroll/financial_handoff_services.py` owns all preparation, review,
  acknowledgment and reconciliation transactions.

## 8. Validation evidence

- Focused PostgreSQL module:
  `apps/payroll/test_p7_s29_s32_financial_handoffs.py`.
- Django system check: passed.
- Migration drift: no changes detected.
- Targeted Ruff: passed.
- `git diff --check`: passed with existing Windows line-ending warnings only.
- Focused PostgreSQL result on the migrated test schema: `7 passed` in 38.39
  seconds, including a real two-thread idempotency race. The two new target
  migrations are recorded applied in PostgreSQL.
- Clean-schema PostgreSQL validation: passed on one uniquely named disposable
  database. The full current migration graph applied from an empty schema,
  including `organizations.0094_p7_s29_s32_payroll_handoff_permissions` and
  `payroll.0005_financialhandoffproposal_financialhandoffline_and_more`.
  Django check and migration-drift check passed; the six handoff tables and four
  idempotency/line/acknowledgment unique constraints were verified directly in
  PostgreSQL. The disposable database was then removed and its absence verified.

The focused module covers finalized-only eligibility, monetary/source pinning,
Tenant and employee lineage, idempotency and concurrency, correction/replacement
lineage, non-effects on every downstream authority, allocation conservation,
unallocated exceptions, permission denial, reconciliation, audit rollback and RTL
UI. The pre-existing 19 unregistered models, 12 namespace mismatches,
`MATERIAL_DOCUMENTS_LINK` gap, six obsolete P6 assertions and two serialized-
restore errors remain separate.

## 9. Preserved gates

No automatic AP recognition, subledger mutation, journal generation/posting, GL
mutation, payment execution/settlement, bank/cash mutation, automatic Project Cost
actual, cross-domain approval, statutory submission, provider integration,
notification, scheduler/queue or production activation is introduced. No accepted
P6 fact is changed.

## 10. Historical P7-S33–S36 handoff scope

This scope was subsequently implemented and is closed out in
`P7_FINAL_ASSURANCE_CLOSEOUT_AND_P8_HANDOFF.md`; the table is retained as the
handoff contract:

| Session | Exact proposed boundary |
| --- | --- |
| P7-S33 | Payroll privacy/minimization, sensitive export and retention/access review across Core, statutory and financial-handoff records; no new financial effect. |
| P7-S34 | Retroactivity and rule/policy-version drift tests across adjustment, statutory correction and all four handoff lineages; explicit stale-source and reversal/replacement reconciliation only. |
| P7-S35 | Golden Payroll cases, cross-family amount/allocation reconciliation, real concurrency/idempotency review, downstream contract-readiness evidence and final preserved-gate verification; no consumer activation. |
| P7-S36 | P7 documentation closeout, readiness review and bounded P8 handoff packet; no P8 implementation or production activation. |
