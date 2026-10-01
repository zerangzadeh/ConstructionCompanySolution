# P4-S01–S06 Estimate/BOQ Depth Implementation Contract

**Date:** 2026-10-01  
**Authority:** Product Owner authorization limited to P4-S01–S06.  
**Status:** implementation complete; focused PostgreSQL verification pending. It does not authorize P4-S07+, P4.1,
financial posting, activation, migration/backfill, or external integration.

## Bounded outcome

This slice extends the existing tenant-scoped Estimate revision evidence with:

1. immutable revision snapshots and side-by-side, planning-only comparison;
2. draft-revision resource composition for labor, material and equipment, with
   controlled same-tenant material/activity/equipment references;
3. recorded (not applied) coefficient and assumption evidence with an explicit
   ordering field and Decimal values;
4. reusable, versioned price-source and rate lineage records; and
5. a non-persistent, formula-free CSV preview profile for the existing estimate
   line shape (`description`, `quantity`, `unit`, `unit_price`, `sort_order`).

The CSV profile is a bounded internal preview contract, not a general spreadsheet
template, XLS/XLSX parser, import execution path, price-book ingestion, or data
load. A preview never creates or changes Estimate, EstimateItem, resource, rate,
source, coefficient, assumption, or any financial record.

## Ownership and invariants

`Estimate` and its revisions remain the sole owner of planning evidence. A
revision is immutable once approved or superseded; P4 records attached to those
revisions must also be immutable. Corrections occur only in a later draft
revision. References must share organization; activity must also share the
estimate project. Material units must use the material's canonical active unit.

Every amount/rate/quantity/percentage uses `Decimal`. Resource rates retain the
source UUID, source version, source reference and license/reference text. No
coefficient or rate is calculated into an EstimateItem in this slice.

No service, view, model, migration, import preview or test may create or mutate
Budget, Commitment, Actual Cost, Payable, Receivable, Revenue, Cash, Treasury,
AP/AR allocation or Accounting journal data. Estimate or contract values are not
changed by these records.

## Authorization and lifecycle

New capability permissions are tenant-scoped and enforced at service boundaries:
view/compare, manage draft composition, manage recorded assumptions, manage rate
lineage and preview imports. They are registered in the catalog and granted only
to existing owner/admin default roles; all operations re-check active membership,
active organization, tenant status, permission and project object scope. Views
are limited to safe reads and CSRF-protected POST preview operations.

## Explicit Product Owner gates (fail closed)

| Gate | Required decision | Behavior before resolution |
| --- | --- | --- |
| P4-G01 | coefficient kinds, calculation order, rounding and escalation/inflation method | records may be captured but cannot be applied or calculated |
| P4-G02 | resource-rate ownership and approval authority | rate records are lineage-only; no rate can price an estimate |
| P4-G03 | external/Iranian price-book source, version and lawful license | no external source ingestion or activation |
| P4-G04 | tenant spreadsheet templates/mappings and approval authority | only the fixed internal CSV preview profile is available; unrecognized/missing mappings reject |
| P4-G05 | estimate-to-budget acceptance, CBS/cost-center and budget authority | no budget handoff, baseline or financial projection |

## Acceptance evidence

Focused tests cover revision immutability; cross-tenant/project denial;
permission denial; resource and source lineage; CSV formula/mapping/value errors;
and asserted absence of financial-domain mutations. Django checks, Ruff, and
migration rollback/reapply are required for schema changes. `ROADMAP.md` is
reconciled only after this evidence passes.
