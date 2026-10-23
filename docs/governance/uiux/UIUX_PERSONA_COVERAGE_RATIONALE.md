# BONIRA UI/UX Persona Coverage Rationale

## Purpose

This document freezes the **persona-granularity rule** used by the BONIRA UI/UX runtime audit so that
future reviews do not oscillate between one persona per job title and a few unrealistically broad personas.

A persona is independent when one or more of the following materially change the user experience:

1. primary goal / job-to-be-done;
2. workflow and lifecycle states;
3. authority / segregation-of-duties boundary;
4. data context and object scope;
5. operational or financial risk;
6. terminology and information density;
7. external versus internal trust boundary.

Persona labels are audit archetypes. They are **not** instructions to create product roles.

## Frozen determining personas

| ID | Persona | Key distinction |
| --- | --- | --- |
| P-01 | Ordinary Tenant User | baseline tenant experience |
| P-02 | Project Operational / Site User | field/project execution |
| P-03 | Procurement Buyer | sourcing/RFQ/order journey |
| P-04 | Equipment/Fleet Specialist | equipment operations and maintenance |
| P-05 | Accountant / GL | accounting journals and statements |
| P-06 | Treasury Specialist | cash/movement/payment-source work |
| P-07 | Billing/Claims/AP-AR Specialist | claims, certificates, settlements |
| P-08 | HR Operations / Personnel Records | employee and organization administration |
| P-09 | ESS Employee | own-data/self-service privacy |
| P-10 | Timekeeping Specialist | attendance/leave/overtime/timesheets |
| P-11 | HSE/Safety Specialist | incidents and safety corrective actions |
| P-12 | Knowledge Curator | publication/reuse/promotion |
| P-13 | Workflow Admin | workflow configuration/administration |
| P-14 | Accessibility Validation Persona | keyboard/landmark/focus evidence |
| P-15 | Tenant Owner | company-level executive oversight |
| P-16 | Tenant Admin | tenant-local access/configuration administration |
| P-17 | Project Manager | project oversight/exception decisions |
| P-18 | Platform Admin | platform-wide governance boundary |
| P-19 | Document Controller | document/version/link lifecycle |
| P-20 | Payroll Specialist | payroll calculation/review/handoff |
| P-21 | Personnel Decree / Employment Records Specialist | effective-dated employment records |
| P-22 | Inventory / Storekeeper | custody/count/transfer/stock |
| P-23 | Contracts & Commercial Specialist | contract/tender/revision/commercial review |
| P-24 | Project Controls / Technical Office Specialist | WBS/progress/estimate/cost-control |
| P-25 | Quality / QA-QC Specialist | quality/NCR/CAPA lifecycle |
| P-26 | External Supplier / Partner Portal User | external procurement boundary |

## Deliberate non-splits

The following are **not** separate personas at this checkpoint unless runtime evidence proves a material UX gap:

- Fixed Asset Specialist: covered initially through Accounting/financial specialist evidence.
- Materials Master Data Controller: covered through Inventory/Storekeeping and Tenant governance; split only if runtime shows a distinct sustained workflow.
- Compliance Officer: covered by separate HSE/Safety and Quality/QA-QC perspectives plus compliance surfaces.
- Support/Service Desk Agent: support surfaces are covered as shared/service workflows; not currently a core determining construction-ERP persona.
- Generic Approver: approvals are tested in their owning domain personas rather than creating one artificial universal approver.
- Executive Project Director: covered initially by Tenant Owner + Project Manager comparison.

## Important separation rules

`Tenant Owner ≠ Tenant Admin ≠ Platform Admin`

`Project Operational User ≠ Project Manager ≠ Project Controls / Technical Office`

`Timekeeping Specialist ≠ Payroll Specialist`

`HR Operations ≠ Personnel Decree / Employment Records ≠ ESS Employee`

`Inventory / Storekeeper ≠ Equipment / Fleet`

`HSE / Safety ≠ Quality / QA-QC`

`Procurement Buyer ≠ Contracts & Commercial ≠ Billing / Claims`

`Ordinary Tenant User ≠ External Supplier / Partner Portal User`

## Employment-record note

The baseline source contains governed effective-dated employment-record logic, including
management permission checks, source document/version requirements and explicit supersession.
The employee-facing UI exposes own employment history. Runtime validation must therefore check
both the employee self-view and whether an appropriate internal management surface exists.
Absence of such a surface is a Product Review question, not permission to invent one during the audit.

## Persistent reference persona rule

The persona set is also a reusable governed reference catalogue.

Once a persona identity is provisioned:

- preserve it for future validation/regression;
- preserve a stable persona/account identifier; a Persian display title is optional;
- preserve traceable authority mapping;
- do not delete/deactivate it as routine test cleanup;
- do not expose secrets;
- do not broaden authority to force PASS.

The administrator-facing product must provide a governed UI to discover/reference these personas.
This does not authorize impersonation.

Canonical policy: `UIUX_REFERENCE_PERSONA_RETENTION_POLICY.md`

## Coverage rule

After Wave E, reconcile:

`UI Dimension × Persona × Module × State`

Each material cell must be one of:

- `DIRECT_RUNTIME_EVIDENCE`
- `REPRESENTATIVE_EQUIVALENCE`
- `STATIC_EVIDENCE`
- `BLOCKED`
- `UTV`
- `NOT_APPLICABLE`

Only material unsupported cells create targeted delta scenarios.


## Checkpoint 15 reconciliation

Actual existing identities are mapped into the canonical persona catalogue where evidence exists.
A proposed `uiux.persona.*` username is a non-binding target alias, not a reason to rename or duplicate an account.

Historical evidence files are not rewritten. Later retention policy supersedes their earlier cleanup instructions prospectively.
