# P4-S38 Project Cost/Controls Closeout and P5 Handoff

**Date:** 2026-10-01  
**Status:** P4-S38 complete. This packet is documentation closeout and a
conditional handoff to P5 planning; it is not P5 implementation or production
activation authority.

## Purpose and boundary

P4-S38 reconciles the verified P4-S01–S37 implementation record with the
Roadmap, active architecture documents, permission/ownership boundaries and the
next source-to-pay phase. It changes no application code, schema, data,
permission, configuration, financial policy or production state.

P4-S38 does not begin P5, authorize a producer, or close any unresolved Product
Owner gate. The next executable unit is P5-S01 only after separate authorization.

## P4 session disposition

| Sessions | Verified disposition |
| --- | --- |
| P4-S01–S06 | Planning-only estimate/BOQ comparison, resource/assumption evidence, immutable price/rate lineage and formula-free preview; coefficient, rate, external price-book and handoff authority remain gated. |
| P4-S07–S13 | Explicit approved-Estimate handoff, versioned CBS/cost-center structure, conserved allocations, immutable accepted budgets, governing pointer, SoD, audit and idempotency. |
| P4-S14–S20 | Inert approved source contracts, append-only commitment/accrual/actual projections, reversal/replacement lineage, incomplete coverage/watermarks, draft forecast snapshots and scoped drill-through; no producer is wired. |
| P4-S21–S25 | Draft schedules, milestones, cycle-safe dependencies, evidence registers and immutable change/rebaseline proposals; acceptance, scoring, contractual impact, rebaseline and earned value remain fail-closed. |
| P4-S26–S30 | Audited expense lifecycle, maker/checker, retained source identity, duplicate/idempotency controls, conserved accepted-budget coding, manual recurrence proposals and advisory snapshots. |
| P4-S31–S34 | Persian RTL controls entry point, bounded accepted-budget/expense comparison, advisory exceptions and audited CSV. |
| P4-S35–S37 | Exact conservation and retry hardening, deterministic PostgreSQL locking, bounded query behavior, and separately permissioned/audited incomplete multi-source reconciliation. |
| P4-S38 | This closeout packet and P5 handoff only. |

## Verified evidence

The S35–S37 focused PostgreSQL acceptance run passed **27 tests**, including the
new conservation, concurrent retry/commitment-cap, tenant/object permission,
provenance/unknown-value, bounded-query, UI/export, migration and retained
Project Cost/Expense regressions. The permission and audit migrations were
rolled back and reapplied successfully. `manage.py check`, migration-drift
check, repository Ruff check and whitespace validation passed.

The broader permission-registry probe still reports the repository's documented
13 pre-existing namespace mismatches; neither new `project_cost` reconciliation
permission is among them. That unrelated gap remains open and is not silently
reclassified as P4 acceptance.

## Retained P4 ownership and fail-closed boundaries

- Accepted budgets remain planning baselines; Expenses owns operational expense
  evidence; Project Cost facts remain inert projections under approved contracts.
- The S35–S37 reconciliation is a non-persistent read model. It keeps sources
  distinct, labels incomplete coverage and exclusions, treats missing evidence
  as unknown rather than zero, and does not establish source authority or a
  financial tie-out.
- No AP, GL, Treasury, cash, settlement, recurrence processor, budget mutation,
  accepted forecast, schedule/risk/delay/change/rebaseline/earned-value
  authority, contractual impact, legacy cutover/backfill or external producer
  is activated.
- P4-G01–G04, unresolved P4-G06–G10 and P4-G11–G18 remain fail-closed. P4-G10
  remains advisory-only and supplies no warning, hard stop, reservation or
  policy enforcement.

## P5 entry gates

P5 remains planned and unstarted. Before P5-S01, Product Owner authorization
must name the approved source-to-pay slice and preserve these gates:

1. Sourcing SoD, confidentiality and bid-privacy rules, including requester,
   buyer, evaluator, award and receiving separation.
2. Supplier/portal identity, invitation, withdrawal and support ownership.
3. RFQ/quote revision/comparison/award lifecycle and immutable source evidence.
4. PO change, service acceptance, supplier invoice and two-/three-way match
   ownership, tolerance policy and discrepancy workflow.
5. Exact Project Cost handoff contract: source/version/line identity,
   occurrence, currency/precision, project/WBS/CBS/cost-center classification,
   idempotency, correction/reversal, coverage and reconciliation behavior.
6. AP/GL/Treasury/Inventory boundaries, migration/backfill strategy, rollout,
   recovery and production activation evidence.

P5 must not infer a commitment, payable, inventory receipt, cash movement,
journal or Project Cost fact from a source record until its separately approved
contract and consuming-domain authority exist.

## Recommended next action

Keep P5 unchanged in the Roadmap until the Product Owner authorizes P5-S01 and
its implementation contract. No follow-on runtime work is implied by this
packet.
