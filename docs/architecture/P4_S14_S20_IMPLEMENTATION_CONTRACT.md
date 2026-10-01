# P4-S14–S20 integrated project-cost implementation contract

**Date:** 2026-10-01. **Status:** implemented and focused PostgreSQL verification
complete. This contract authorizes and describes P4-S14–S20 only. P4-S21+, any
production activation, external producer integration, legacy backfill/cutover and
replacement of `Project.estimated_budget` / `actual_budget` remain excluded.

## Delivered steps

| Step | Delivered boundary |
| --- | --- |
| P4-S14 | Tenant-scoped, versioned producer-source contracts with an inert draft state, independent approval, exact schema/policy references, payload identity and database immutability after approval. |
| P4-S15 | Append-only classified commitment facts with exact source/event/occurrence/line identity, CBS/WBS/cost-center validation, idempotency and authorized/relieved/open projection. |
| P4-S16 | Append-only accrual and actual-cost projections. Financial-evidence requirements are contract-controlled; exact reversal and reversed-accrual replacement prevent accrual/invoice double counting. No GL, AP, Treasury or source record is mutated. |
| P4-S17 | Cross-contract economic-event/line deduplication, correction lineage, source drill-through, coverage watermarks and explicit incomplete coverage. Complete production coverage is fail-closed. |
| P4-S18 | Immutable forecast draft snapshots with cutoff, governing budget, source watermark, actual, open commitment, committed ETC, uncommitted ETC and EAC. |
| P4-S19 | Permission-scoped Persian/RTL project-detail summary and source drill-through. Missing coverage is visibly incomplete, never represented as certified zero cost. |
| P4-S20 | Dedicated permissions/catalog/default grants, audit actions, PostgreSQL immutability triggers, focused service/tenant/permission tests and migration rollback/reapply evidence. |

## Runtime and ownership boundary

The implemented services are a rebuildable Project Controls projection, not a
parallel ledger. A fact can be recorded only against an independently approved,
code/version-specific source contract and the project's governing accepted budget.
Classification must use that budget's locked leaf CBS, active project WBS,
applicable cost center and exact currency. Approved source contracts, all facts and
forecast snapshots are database-immutable. Corrections are additive reversals;
idempotent retries return the existing record and payload conflicts fail.

No existing Procurement, Inventory, Expense, Payroll, Equipment, Billing,
Subledger, Treasury or Accounting service calls this boundary. Registering and
approving a contract makes the internal service usable but does not activate an
external or production producer. There is no backfill, scheduler, outbox, API,
external integration, journal posting or legacy-field switch.

Coverage can be marked not-started or partial with a watermark and exception.
`complete` remains a reserved schema state that the service refuses until a
separately authorized producer set, cutoff and reconciliation acceptance exist.

The project-detail page exposes a read-only cost card only to actors with
`project_cost.view` and applicable project scope. Mutation remains service-only;
there is no UI that can create or approve a source contract, record a fact, mark
coverage or prepare a forecast.

## Fail-closed Product Owner gates

| Gate | Enforced remainder |
| --- | --- |
| P4-G01–G04 | No coefficient/rate calculation, price-book ingestion or spreadsheet-template activation is introduced. |
| P4-G06 | Existing accepted-budget authority remains mandatory. This package does not broaden initial/revision budget authority or rebaseline policy. |
| P4-G07 | No starter CBS, default cost center or allocation basis is invented; facts must use the governing budget's explicit locked classification. |
| P4-G08 | No FX or inferred rounding exists; source currency must exactly equal the governing budget currency and financial evidence is required where the approved contract declares it. |
| P4-G09 | No rebaseline, return/withdrawal or superseded-source behavior is added. Cost corrections use append-only reversal/replacement lineage only. |
| P4-G10 | No warning, hard stop, reservation or downstream transaction control is implemented. Forecast acceptance/approval is unavailable pending forecast cadence and approval policy. |

The exact remaining Product Owner decisions are: producer selection and production
activation per source domain; detailed recognition/reconciliation mapping for each
real producer; forecast cadence, approval authority and SoD; numeric precision or
rounding rules beyond exact stored Decimal/currency matching; overrun warning versus
hard-stop policy; and legacy coverage, pilot, cutoff, backfill, reconciliation and
rollback acceptance. These gates do not block the independent internal projection
foundation delivered here.

## Verification

- 7 retained P4-S07–S13 PostgreSQL service tests plus 5 P4-S14–S20 tests cover
  producer ordering/approval SoD, idempotency conflict, commitment relief,
  accrual reversal/actual replacement, source evidence, coverage, forecast math,
  cross-Tenant denial, database immutability and the permission-scoped UI state.
- The Projects migration suite proves rollback from `0007` to `0006` and reapply,
  in addition to the retained `0006` rollback/reapply proof.
- `manage.py check`, migration drift detection and targeted Ruff checks pass.
- The permission-registry audit retained 5 passing tests and 11 passing role
  subtests. Its 3 known repository-wide failures remain limited to the pre-existing
  model-registration, namespace and `MATERIAL_DOCUMENTS_LINK` gaps; this package
  introduced no additional reported gap.
