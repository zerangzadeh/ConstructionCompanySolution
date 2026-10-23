# BONIRA UI/UX Functional Persona Coverage Correction — Checkpoint 12

## Decision

Status: `FUNCTIONAL_PERSONA_GRANULARITY_REVISED_BEFORE_RUNTIME_EXECUTION`

A second persona review was performed against the construction-ERP module/journey inventory.

The review found that five original archetypes were too broad and seven determining user
perspectives were still missing.

## Refined existing personas

- `P-04`: Inventory + Equipment split; P-04 is now Equipment/Fleet.
- `P-07`: narrowed to Billing/Claims/AP-AR.
- `P-08`: narrowed to HR Operations / Personnel Records.
- `P-10`: Timekeeping separated from Payroll.
- `P-11`: HSE/Safety separated from Quality/QA-QC.

## Added personas

- `P-20` Payroll Specialist
- `P-21` Personnel Decree / Employment Records Specialist
- `P-22` Inventory / Storekeeper
- `P-23` Contracts & Commercial Specialist
- `P-24` Project Controls / Technical Office Specialist
- `P-25` Quality / QA-QC Specialist
- `P-26` External Supplier / Partner Portal User

## Added targeted runtime scenarios

- `RV-029` Personnel decree / effective-dated employment record lifecycle
- `RV-030` Contract and commercial administration lifecycle
- `RV-031` Project controls, estimates and technical-office oversight
- `RV-032` External supplier / partner procurement portal

Runtime persona count: `26`

Audit-specific runtime scenario count: `32`

Wave count remains: `5`

## Governance effect

- Static audit rerun: `NO`
- Existing 108 findings changed automatically: `NO`
- Existing root patterns reset: `NO`
- Product roles created: `NO`
- Permission codes created: `NO`
- Remediation authorized: `NO`
- CEP-078 executed: `NO`
- CEP-079 executed: `NO`
- Production action: `NO`
- Git write: `NO`

## Employment-record specific decision

The baseline contains governed effective-dated employment-record services, while the employee-facing
surface exposes own employment history. `RV-029` must first verify whether an internal governed
management surface exists for the authorized personnel specialist.

If it does not exist:

`NEEDS_PRODUCT_REVIEW`

Do not fabricate a route, direct model UI or unauthorized management path.

## Closure

Checkpoint result:

`FUNCTIONAL_PERSONA_COVERAGE_SUFFICIENT_FOR_RUNTIME_PLANNING`

Further persona splitting requires runtime evidence of a materially different goal, authority,
workflow, data context or risk. Job titles alone are not sufficient.
