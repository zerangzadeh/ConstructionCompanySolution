# P4-S07–S13 Budget-Preparation Implementation Contract

**Date:** 2026-10-01  
**Authority:** Product Owner authorization limited to P4-S07–S13.  
**Status:** implementation complete; focused PostgreSQL acceptance evidence passed.
This contract does not authorize P4-S14+, producer integration, production
activation, or legacy cutover/backfill.

## Bounded outcome

This slice implements planning-only Project Controls evidence:

1. Tenant-owned, versioned and explicitly locked CBS/cost-center structures,
   separate from WBS and the Chart of Accounts.
2. A complete manifest pinned to the current approved Estimate revision and every
   source line, with explicit included/excluded disposition.
3. Conserved Decimal allocations from each included source line to a leaf CBS,
   active project WBS and, when explicitly required, a cost center.
4. Draft/submitted/accepted budget versions, predecessor lineage, one governing
   accepted version per project, durable handoff identity and payload hash.
5. Permission-checked preparation/submission/acceptance, direct maker-checker
   enforcement, project-row concurrency serialization, stale-predecessor conflict,
   audit evidence, database-level accepted-payload immutability and a bounded
   planning read model.

Budget acceptance does not create or mutate a commitment, actual cost, payable,
receivable, revenue, cash, Treasury movement, AP/AR allocation, Accounting journal,
forecast, expense, payment or contract value. `Project.estimated_budget` and
`Project.actual_budget` remain unchanged compatibility fields and are not switched,
backfilled or retired by this slice.

## Lifecycle and authority

`draft -> submitted -> accepted` is the only delivered forward lifecycle.
Submission requires every pinned Estimate line to be explicitly included with an
exactly conserved allocation or excluded with a reason. Acceptance re-reads and
locks the budget/project/governing pointer, prohibits the submitter from accepting,
requires `budgets.accept`, verifies the frozen payload hash and rejects a stale
predecessor. Identical durable-handoff retries return the existing record; a changed
payload under that identity conflicts.

Only Tenant Owner/Tenant Admin system roles receive the new permissions by default.
Object scope, active membership, active Tenant state and the selected project are
still intersected at every service boundary. Custom grants remain governed by the
existing authorization model.

## Product Owner Gates retained exactly

| Gate | Unresolved decision | Fail-closed behavior |
| --- | --- | --- |
| P4-G06 | Named initial/revision budget authority, grant policy, eligible Estimate revisions and final handoff approval/SoD governance | No implicit authority exists. Services require dedicated permissions, current approved Estimate evidence, an explicit governance reference and independent acceptance; Self-Approval is prohibited. |
| P4-G07 | Starter CBS hierarchy, cost-center applicability and allowed mapping/allocation bases | No starter codes, default cost center or allocation basis is invented. A handoff must select a locked Tenant structure, leaf CBS, active project WBS, explicit basis reference and explicit cost-center-required choice. |
| P4-G08 | Effective currency/precision/rounding policy for budget handoff | Currency is snapshotted only from authoritative `OrganizationSettings`; an explicit rounding-policy reference is mandatory. This slice performs no FX, conversion or policy-derived rounding. Missing configuration/reference blocks creation. |
| P4-G09 | Baseline revision/change governance beyond predecessor lineage, including return/withdrawal, superseded-source eligibility and rebaseline reasons | Only explicit draft/submitted/accepted versions and stale-predecessor protection are delivered. No silent rebaseline or accepted-history edit is possible; broader change governance remains closed. |
| P4-G10 | Warning versus hard-stop behavior for overruns or downstream operations | No warning, quota, reservation or blocking control is implemented. The planning baseline cannot block or authorize any financial/operational transaction. |

P4-G01–G04 remain open for coefficient/rate/price-book/spreadsheet behavior.
P4-G05 is closed only for this bounded, explicit Estimate-to-budget planning
handoff; it does not close G06–G10 or authorize integrated project cost.

## Acceptance evidence

- P4-S01–S06 prerequisite: 3 focused PostgreSQL tests passed.
- P4-S07–S13: 7 focused PostgreSQL service tests cover mapping completeness and
  conservation, Tenant/object/permission/SoD denial, idempotent retry,
  stale-predecessor concurrency protection, accepted-history immutability,
  missing authoritative currency, planning evidence and financial-boundary
  non-mutation.
- One PostgreSQL migration test rolls `projects` back to `0005` and reapplies
  `0006_p4_s07_s13_budget_preparation`.
- Three targeted permission/catalog tests with 11 role-default subtests pass.
  The three broader registry architecture assertions retain their pre-existing
  document/material/model-registration, namespace and
  `MATERIAL_DOCUMENTS_LINK` gaps; the new `budgets` and `cost_structures`
  resources add none of those failures.
- Django checks, migration-drift detection and targeted Ruff pass. No P4-S14+
  test or behavior is included.
