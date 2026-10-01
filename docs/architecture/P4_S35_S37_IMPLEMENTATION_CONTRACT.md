# P4-S35–S37 Cost Evidence Hardening and Reconciliation Contract

**Authorized:** 2026-10-01. **Boundary:** P4-S35 through P4-S37 only. P4-S38
and P5 are not authorized.

## Delivered safe scope

| Session | Delivered runtime behavior |
| --- | --- |
| P4-S35 | Exact expense retry payload matching; accepted-budget-pinned expense assessment; coded-dimension conservation for Project Cost commitment relief, adjustments, reversals and accrual replacement. Existing database immutability remains authoritative. |
| P4-S36 | Deterministic project/control/source lock order, locked re-read of reversal/replacement evidence, serialized commitment caps, and exact concurrent idempotent expense/source-contract retry behavior on PostgreSQL. |
| P4-S37 | Separately permissioned and audited Persian RTL read model and CSV that place the governing accepted budget, identically pinned approved/recorded expense allocations and existing inert Project Cost actual facts side by side without merging their authority. Query count is bounded independently of evidence-row volume. |

## Reconciliation meaning and provenance

The reconciliation is deliberately incomplete. It exposes exact source-contract
identity/version/model, reconciliation-policy reference, coverage status and
watermark without exporting raw operational source identifiers. Project Cost
facts do not currently retain a budget-version key, so their amounts are labelled
`uncomparable` to the governing budget even when their currency and coding match.
A numeric expense-versus-inert-actual difference is `unresolved` evidence only;
it is not a duplicate decision, accounting tie-out, posting control, budget
variance policy or assertion that either source is authoritative.

Missing evidence is `unknown`, never zero. Unallocated expenses, allocations
pinned to another budget, non-actual Project Cost facts and currency-mismatched
facts are counted and labelled as excluded. Coverage remains `incomplete` and
source equivalence remains `not_established` in the UI, CSV and audit metadata.

## Access, separation and audit

`project_cost.reconciliations_view` and
`project_cost.reconciliations_export` are distinct catalogued permissions with
active-membership and project-object scope. Every view and export records an
append-only audit event; export evidence includes project/budget scope, digest,
byte count and explicit incomplete/equivalence labels. Existing direct maker/
checker separation remains mandatory for budget acceptance, source-contract
approval and expense approval. Reconciliation itself is read-only and grants no
transition or mutation authority.

## Fail-closed boundary

Accepted budgets remain planning authority only. Approved/recorded expenses
remain operational cost evidence only. Existing `ProjectCostFact` rows remain
inert classified projections under their approved contracts. No service in this
package creates or activates a producer, payable, journal, Treasury/cash event,
settlement, recurrence processor, budget mutation, accepted forecast, schedule/
risk/delay/change/rebaseline/earned-value authority, or contractual impact.

P4-G01–G04, unresolved P4-G06–G10 and P4-G11–G18 remain fail-closed. In
particular, P4-G10 supplies no warning, hard stop, reservation or policy
enforcement. P4-S38 was subsequently completed as documentation-only closeout;
P5 still requires separate Product Owner authorization.

## Acceptance evidence

Focused PostgreSQL tests cover evidence conservation, exact retries, concurrent
commitment caps/row locking, permission and Tenant/project isolation, immutable
source regressions, bounded query count, incomplete provenance and unknown rather
than zero semantics. New permission and audit-choice migrations must roll back
and reapply cleanly. Django checks, migration drift and Ruff must pass.

The documentation-only P4-S38 disposition and P5 entry conditions are recorded
in `P4_S38_CLOSEOUT_AND_P5_HANDOFF.md`.
