# BONIRA — Development Synthetic Closure Authorization

Decision ID: DEV-SYNTHETIC-DATA-AUTH-20261020-V2
Human Decision Authority: Azam Zerangzadeh
Decision date: 2026-10-20
Environment: Development / Non-Production only

## Factual Development premise

For the bounded BONIRA Development closure of CEP-057 and CEP-058:

- No real organizational Leave opening history is intended to be migrated.
- No real organizational Payroll/YTD historical opening population is intended to be migrated.
- Therefore the real authoritative historical opening population is ZERO for both CEPs.

## Approved purpose of this package

The attached synthetic data is approved solely to validate and evidence:

- source-to-target mapping;
- opening/backfill mechanics;
- policy/year/cutoff binding;
- component mapping;
- correction lineage;
- reconciliation and control totals;
- exception behavior;
- repeatability and idempotency;
- rollback/recovery;
- focused and affected regression tests.

The synthetic rows are not real organizational history and must never be described as Production data or real employee balances/payroll.

## Identity resolution — no Human follow-up required

The package contains DEV-HR-001 through DEV-HR-010.

Codex is authorized to:
1. locate the 10 already-verified CEP-029 Development WorkRelationship identities;
2. sort them by stable WorkRelationship UUID ascending;
3. map DEV-HR-001..010 to ordinal 01..10;
4. persist the resulting mapping as evidence.

This is an explicit synthetic Development mapping approved by the Human Decision Authority. It is not identity inference.

If the repository no longer contains exactly 10 usable CEP-029 Development relationships, Codex is authorized instead to create a dedicated set of 10 synthetic Development Person/Employee/WorkRelationship fixtures using existing canonical Development seed/services, then map DEV-HR-001..010 to those records. No additional Human confirmation is required.

## Leave policy resolution — no Human follow-up required

DEV-LEAVE-POLICY-v2 is approved as the Development-only policy fixture.

If persisted policy/version records are required, Codex is authorized to create/reuse Development-only records matching the supplied policy document through existing canonical services.

## Payroll component resolution — no Human follow-up required

For each component in CEP058_COMPONENT_CROSSWALK_SYNTHETIC.csv:

- resolve an existing Development component with the exact target_component_code if present;
- otherwise create a Development-only component through the existing canonical payroll component service;
- use the operational kind supplied in the crosswalk;
- do not add statutory rates or Production legal meaning.

## Payroll year / cutoff resolution

Approved:
- payroll year: DEV-PY-2026-A
- inclusive start: 2026-01-01
- inclusive end: 2026-12-31
- as-of: 2026-09-30
- continuation/cutover: 2026-10-01
- currency: IRR

## Applicability rule for canonical migration AC/DoD

If a CEP-057 or CEP-058 clause is specifically about reconciling a non-zero real organizational history, apply:

`N/A — ZERO AUTHORITATIVE DEVELOPMENT HISTORY`

This is an explicit Human applicability decision for Development only.

Do not falsely mark an inapplicable real-history condition as PASS.

All technical migration/backfill behavior, controls, retry/idempotency, rollback/recovery, traceability, tests and evidence remain mandatory and must PASS.

## Development implementation authority

Codex is authorized to perform the bounded Development-only data creation/backfill/migration needed for CEP-057 and CEP-058 using this package.

If existing canonical implementation requires a minimum additive Development schema migration to support the already-approved CEP scope, that migration is authorized only when:
- it is strictly necessary;
- it does not introduce new business semantics;
- it is attributable to CEP-057 or CEP-058;
- Production is not touched.

If canonical Migration Impact is NONE and no schema change is necessary, do not create one.

## Self-repair rule for synthetic fixtures

If a supplied synthetic row conflicts with an existing model validation constraint, Codex may adjust the synthetic fixture deterministically to the nearest valid Development value while preserving:
- the intended operational kind;
- the approved cutoff;
- the control-total logic;
- the synthetic-only boundary.

Record any such adjustment in evidence. No routine Human confirmation is required.

## Hard boundaries

- No Production action.
- No Production data.
- No Production Certification.
- No Production Human Sign-off.
- No CEP-069..079 execution.
- No fabricated real organizational history.
- No invented statutory, legal, tax, insurance or Production policy semantics.
- No weakening of tests, AC or DoD.
