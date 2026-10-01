# P3-S32 Treasury/Subledger Closeout and P4 Handoff

**Date:** 2026-10-01  
**Status:** P3-S32 documentation closeout complete. This packet is a handoff to
P4 planning; it is not P4 implementation or production-activation authority.

## Purpose and scope

P3-S32 reconciles the delivered Treasury, statement/reconciliation and AP/AR
subledger work with the next Project Cost/Controls phase. It records verified
implementation evidence, unresolved acceptance and activation gates, and the
ownership constraints P4 must preserve.

It changes no application code, schema, data, permissions, configuration,
financial policy or production state.

## P3 closeout status

| P3 scope | Verified disposition |
| --- | --- |
| S01--S04 | Accepted Treasury/subledger ownership and transition decisions are recorded in the [decision packet](P3_S01_S04_TREASURY_SUBLEDGER_DECISION_PACKET.md). |
| S05--S11 | Native Tenant-scoped Treasury accounts, movements, cheque evidence, mapping and the synchronous Treasury-to-Accounting producer are implemented. |
| S12--S17 | Bounded payment request, advance and cash-return settlement evidence is implemented without scheduling, numeric-policy or activation assumptions. |
| S18--S22 | Bounded statement evidence, exact duplicate controls, clearing/correction and bank reconciliation are implemented without provider integration, production limits or Accounting mutation. |
| S23--S27 | Immutable AP/AR obligations, Treasury-linked allocation/reversal, exact unbucketed aging and reconciliation evidence are implemented. Q01--Q04 remain decisions only; unavailable recognition/posting and write-off approval/reversal remain disabled. |
| S28--S29 | Persian-first Treasury/subledger workbench implementation is complete, but its Product Owner acceptance remains pending. |
| S30--S31 | Independent Treasury and AP/AR reconciliation review is complete and accepted. Eight focused controls/UI tests and three retained Treasury/subledger/Accounting regressions passed; the [implementation contract](P3_S30_S31_IMPLEMENTATION_CONTRACT.md) records the resolved isolated-test-database investigation. |
| S32 | This documentation closeout and P4 handoff are complete. |

No P3 implementation result authorizes production activation, legacy `Payment`
or claim-settlement cutover/backfill, provider or external integration,
background processing, source recognition, Accounting production, write-off
approval/reversal, numeric thresholds/tolerances/limits, or
`MATERIAL_DOCUMENTS_LINK` remediation.

## Retained P3 ownership and safety boundaries

- Treasury owns cash accounts, instruments, movements, statements, clearing and
  cash-to-GL reconciliation evidence. A movement or clearing is not an
  Accounting journal or project-cost fact.
- Subledgers own obligations, exact Treasury-linked settlements, aging and
  subledger reconciliation evidence. They never select or mutate cash-account
  postings.
- Accounting owns journals, fiscal periods and ledger correction. P3's
  reconciliation/review evidence does not authorize a P4 journal, adjustment or
  posting path.
- Tenant isolation, active-membership and Tenant-status checks, object scope,
  CSRF, append-only audit, immutable history, idempotency and direct
  maker-checker enforcement remain mandatory at every consuming boundary.
- Settlement UI and services retain exact Treasury clearing lineage. P4 must not
  replace it with a cash-account selector or derive a second settlement record.

## P4 handoff

The authoritative target for P4 is [P4.0/P4.1 in the Roadmap](../../ROADMAP.md)
and the accepted-as-target-only
[budget/CBS/cost-center ADR](ADR_P0_S05_BUDGET_PROJECT_COST.md). P4 owns an
accepted budget baseline, CBS and cost-center classification, source-fact
classification, forecast assumptions and project-cost read models. It must not
become a parallel ledger or overwrite source-domain history.

P3 can become a future source of *paid-cash* and settlement evidence only after
P4 defines a tenant/project/WBS/CBS/cost-center classification and a versioned
producer contract. Cash is never an automatic actual cost: an advance, asset
purchase, unallocated cash movement or AP/AR allocation has no implied
project-cost classification. AP/AR obligations and allocations likewise do not
establish a P4 cost fact, recognition basis, commitment, accrual or budget
consumption.

Before any P4 consumer reads P3 evidence, its separately authorized package must
define the exact source identity/version, direction, occurrence, effective date,
currency/precision basis, project scope, classification/version, accounting
period where applicable, correction/reversal lineage, idempotency key, access
scope and reconciliation behavior. Missing classification, recognition or
coverage is an explicit exception/incomplete view, never zero actual cost or a
default allocation.

## P4 entry gates retained

1. P4.0 requires its own Product Owner decisions on licensed price-book sources,
   coefficient policy, rate ownership and safe import templates.
2. P4.1 requires an explicit accepted estimate-to-budget handoff, CBS and
   cost-center policy, project-cost classifications, budget authority, forecast
   cadence and warning-versus-hard-stop behavior.
3. Producer-domain contracts are required before commitments, accruals, actuals,
   paid cash, inventory valuation, payroll, equipment and source-to-cost
   reconciliation can be represented. No P3 path supplies those missing contracts
   by implication.
4. P4 must preserve the existing expand/migrate/switch/validate/approved-cutover
   approach for legacy `Project.estimated_budget` and `Project.actual_budget`.
   P3-S32 does not authorize a migration, backfill, switch or retirement.

## Recommended next authorized unit

The next candidate is a separately authorized P4-S01 planning/implementation
contract using only the minimum context above, P4.0/P4.1 Roadmap sections and
the P0-S05 ADR. It must not start until the Product Owner explicitly authorizes
that P4 scope. This handoff neither accepts P3-S28--S29 nor opens any P3
activation gate.
