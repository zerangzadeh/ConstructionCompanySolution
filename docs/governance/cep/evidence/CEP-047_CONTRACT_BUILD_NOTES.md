# CEP-047 bounded contract build

These are implementation notes, not new product policy. The canonical prompt and
the byte-identical retained Human mapping resolution govern the build.

## Source-specific evidence

| Contract | Native source identity | Value/version evidence | Explicit inverse lineage |
|---|---|---|---|
| INT-B04 | InventoryValuationEvent, posted project issue and Project Controls envelope | Native quantity/unit, finalized value, source reference/version and monetary-policy IDs | Valuation reversal_of plus matching stock reversal_of |
| INT-B05 | EquipmentCostAllocation and reviewed Project Cost envelope | Finalized allocation, approved usage, measure, rate snapshot, rate/policy version, project/site/activity | Native correction_of exact inverse; reviewed envelope supersedes where present |
| INT-B06 | Reviewed FixedAssetSourceEnvelope for finalized depreciation line | Depreciation run/line, asset identity, book/version and separately approved attribution mapping | Native run reversal_of with same asset line; envelope supersedes where present |

Raw receipts, inventory count adjustments, equipment identity and generic asset
capitalization/disposal/transfer records do not establish these producer contracts.
Unsupported or ambiguous correction evidence fails closed. No relationship is
inferred from record numbers, names, dates, mutable current asset project, or
domain similarity.

## L2 candidate and target authority

`prepare_actual_candidate` derives an in-memory candidate. It creates no source,
recognized fact, approval, journal, settlement or candidate lifecycle record.
No source save hook, signal, endpoint or automatic recognition path is wired.

`consume_actual_candidate` is an explicit Project Controls operation using the
existing `project_cost.facts_record` authority and `record_project_cost_fact`.
It re-reads the approved tenant contract, native source and approved policy
binding inside the target transaction. The existing target service remains
authoritative for budget, coded dimensions, currency, financial evidence and
exact inverse constraints. New effects append facts; finalized facts are not
updated or deleted. This adds no approval depth or Accounting recognition rule.

Registered code-owned bindings match all approved contract policy references.
They must validate the approved mapping/classification, cutoff/effective date,
unit/value/rate/book basis and versioned attribution. No tenant executable policy
is accepted. The registry ships empty; there is no permissive fallback, inferred
date/allocation/rate or rounding rule. Inexact values for the existing two-place
fact model are rejected. EXT-0006/0007/0008 remain activation requirements; test
bindings and synthetic policies are never tenant activation evidence.

## Idempotency, failure and reconciliation

The occurrence identity has exactly the SPEC-008 components: producer contract,
source type, source identity, source version and ACTUAL recognition type. The
native version fingerprint pins immutable source evidence; selected original
native version labels and unit/rate/book lineage are retained in successful
append-only audit metadata. Line-specific occurrence keys do not expand the
canonical source identity. Same-identity changed payloads and unlinked version
or contract changes fail closed.

Attempts commit before target mutation. Target facts and success evidence commit
atomically; errors roll them back and retain a separate failure audit. Retries
reload eligibility, permissions, contract and policy. Replays return the original
facts without reactivating inactive history. Explicit native predecessors require
an already recognized predecessor and preserve exact target inverse lineage.

Reconciliation is read-only. It identifies native version/activity, mapped and
target amounts, approved basis/cutoff/attribution, target payload/lineage gaps,
explicit successors and corresponding target inverses. It creates no repair or
financial authority. Audit evidence identifies integration attempts; existing
ProjectCostFact records remain the recognized Project Cost authority.

## Validation boundary

Focused tests exercise unit identity, real target transactions, all three native
domain workflows, exact inverses, replay, source/policy drift, failure rollback,
retry and read-only reconciliation. Existing source and projection scenarios are
affected regression checks. Legacy fixture authority is adapted only in test
wrappers; production defaults and historical shared fixtures are unchanged.

Test-database historical migration bootstrap is harness setup, not CEP migration
verification or Development migration execution. There are no new model/schema,
migration, permission-catalog/default-grant or UI changes. Performance/concurrency
runtime remains UTV. No production, Human Sign-off or Production Certification
authority is supplied by this build or its evidence.

## Resumed validation corrections

The native reader supplies its own atomic boundary for standalone callers as well
as nesting in target transactions. Reversal lifecycle notes are excluded from the
immutable financial version. Values with native trailing zeroes are normalized to
two places only after exact equality has proved that no rounding is needed.
Preexisting authoritative facts with no successful integration lineage deny new
recognition and are exposed by read-only reconciliation, subject to existing target
project scope. Existing source workflows, target service constraints and authority
catalogues remain unchanged. Final focused and affected regression evidence is
linked from the Completion Report; initial failures remain attributable artifacts.
