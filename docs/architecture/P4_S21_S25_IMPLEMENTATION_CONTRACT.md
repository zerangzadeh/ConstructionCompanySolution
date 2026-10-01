# P4-S21–S25 Schedule, Risk, Change, and Rebaseline Implementation Contract

**Status:** SAFE FOUNDATION IMPLEMENTED AND VERIFIED; POLICY-DEPENDENT ACTIONS FAIL CLOSED  
**Authorized:** 2026-10-01 by the Product Owner for P4-S21–S25 only  
**Boundary:** P4-S26+, external scheduler integration, production activation,
legacy replacement, contractual/financial mutation, and earned-value calculation
are excluded.

## 1. Delivered session disposition

| Session | Delivered safe scope | Deliberately blocked remainder |
| --- | --- | --- |
| P4-S21 | Tenant/project-scoped immutable schedule revisions with explicit dates, data date, calendar/assumption references, predecessor lineage, occurrence idempotency, version locking and dedicated permissions/audit. | Baseline acceptance, calendar calculation, resource loading, critical path and external import/export. |
| P4-S22 | Immutable schedule items, zero-duration milestones, optional WBS linkage and four closed dependency types with lag evidence, same-revision integrity, duplicate protection and cycle rejection. | Automated scheduling semantics, float/criticality calculation and external scheduler synchronization. |
| P4-S23 | Immutable constraint/issue/risk/delay observations with required owner/evidence, delay observation dates, optional schedule-item linkage, and serialized append-only open/closed/reopen history. | Risk scoring, probability/impact matrices, delay responsibility and contractual/EOT conclusions. Responsibility remains `undetermined`; contractual impact remains `unassessed`. |
| P4-S24 | Immutable, idempotent project-change proposals with separate schedule/cost narratives and evidence. | Change approval, Variation/Change Order, Claim/EOT, contract value, billing, accounting and project-cost mutations. Contractual impact remains `unassessed`; financial effect remains `observation_only`. |
| P4-S25 | Immutable, idempotent rebaseline proposals linking a retained accepted baseline, candidate draft, optional change proposal, reason and evidence; retained accepted schedule history has a database immutability guard; focused PostgreSQL and rollback/reapply evidence. | Baseline/rebaseline acceptance and authority. No service can create a new accepted baseline under the current gate. |

## 2. Ownership and invariants

- Project Controls owns only planning schedule revisions, dependencies, control
  observations, change proposals, and rebaseline proposals.
- Contracts/P6 owns contractual entitlement, Variation/Change Order, Claim and
  EOT. Billing owns measurement/claims, Accounting owns journals, and source
  domains retain their own operational facts. This package invokes none of them.
- Every object is Tenant/project scoped. Service boundaries require active
  membership, active Tenant state, the dedicated permission and object scope.
- Occurrence keys and stable payload hashes make schedule revisions, register
  observations, change proposals and rebaseline proposals idempotent; mismatched
  retries fail. Project row locks serialize version assignment and register row
  locks serialize status history.
- Schedule payload, register/status evidence, change proposals and rebaseline
  proposals are append-only at model and PostgreSQL levels. Accepted schedule
  rows are database-immutable.
- Dependency endpoints must share one schedule/project/Tenant, cannot self-link,
  and cannot create a directed cycle. Milestone start and finish must match.
- Delay responsibility and contractual impact cannot be changed from their
  fail-closed values. Change proposals cannot acquire contractual or financial
  authority.

## 3. Permissions and defaults

Safe permissions are `project_schedules.view`, `project_schedules.prepare`,
separate `view`/`manage` permissions for control registers, and separate
`view`/`propose` permissions for changes and rebaselines. Read snapshots expose
each section only when its own permission is present. They are granted only to the same owner/admin
default boundary as the preceding P4 planning controls.

The catalog also registers `project_schedules.accept`,
`project_changes.approve`, and `project_rebaselines.accept`, but no default role
receives them. Even an explicit test grant reaches a hard-disabled service gate;
catalog presence is not activation or authority.

## 4. Exact open Product Owner gates

| Gate | Decision required before activation |
| --- | --- |
| P4-G11 schedule depth/integration | Supported calendar, duration/lag semantics, resource loading, critical-path/float rules, import/export formats, external scheduler/provider, reconciliation and cutoff ownership. |
| P4-G12 baseline authority | Initial baseline maker/checker roles, required evidence, SoD, valid project state, acceptance/rejection transitions, governing pointer, and correction/reversal behavior. |
| P4-G13 risk policy | Risk taxonomy, qualitative/quantitative scales, scoring formula, thresholds, review cadence, aggregation and accountable owner. |
| P4-G14 delay responsibility | Who may assess responsibility, required evidence, dispute/revision lifecycle, SoD and whether any classification may be shared with P6. |
| P4-G15 change approval | Maker/checker roles, workflow, thresholds, valid decisions, supersession/withdrawal, and explicit handoff—not mutation—to P6/P4.1. |
| P4-G16 contractual impact | Exact boundary and reviewed handoff to Variation/Change Order, Claim and EOT; no Project Controls field may itself establish entitlement. |
| P4-G17 rebaseline authority | Required accepted source baseline, eligible approved change evidence, approver/SoD, comparison/retention rules, governing-pointer switch and rollback semantics. |
| P4-G18 earned value | Approved physical-progress authority, budget/schedule mapping discipline, status date, formulas, calendar/currency/rounding policy and reconciliation. Until then no EV metric is calculated. |

## 5. Runtime and UI disposition

The application service layer can create and permission-scope a read snapshot of the safe draft/evidence
objects and record controlled register transitions. P4-S21–S25 adds no end-user
screen: broad schedule/change UI, comparisons, exception views and exports remain
the separately authorized P4-S31–S34 tranche. Django Admin is not registered as
an alternate mutation path.

## 6. Verification

Seven focused PostgreSQL service/concurrency tests cover fail-closed default grants,
independent read permissions,
cross-Tenant denial, idempotency under simultaneous submission, serialized
stale-transition rejection, milestone/date rules, dependency-cycle integrity,
delay evidence, fail-closed responsibility/impact, hard-disabled acceptance, and
database immutability. One focused migration test
rolls back to projects `0007` and reapplies `0008`, proving the schedule/control
tables and triggers can be removed and recreated. Django system checks,
no-pending-migration checks, and scoped Ruff checks pass.
