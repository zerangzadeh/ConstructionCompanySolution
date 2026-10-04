# P7-S01–S05 Workforce Foundation Implementation Record

**Status:** Product Owner accepted. Focused PostgreSQL and clean-schema
migration validation passed. This record covers only P7-S01–S05. P7-S06–S12
was subsequently Product Owner accepted in
`P7_S06_S12_TIME_AND_ATTENDANCE_IMPLEMENTATION.md`. P7-S13–S22 was subsequently
Product Owner accepted in `P7_S13_S22_CORE_PAYROLL_IMPLEMENTATION.md`; P7-S23–S28
are subsequently Product Owner accepted; P7-S33–S36 is subsequently Product Owner
accepted, consolidating P7-S01–S36 as complete within documented non-production
boundaries. P8 remains planning-only and production activation remains unauthorized.

## Delivered boundary

- **S01:** reconciled the retained Workforce entry boundary. `User` remains an
  authentication identity; an `Employee` remains a tenant Workforce record and
  may have no linked user. Position, department, team, skills and competencies
  are responsibility/evidence only and never grant a system permission.
- **S02:** tenant-scoped `Skill` and `Competency` catalogues plus immutable,
  effective-dated `EmployeeSkillRecord` proficiency history. The service locks
  overlapping candidates, rejects overlapping intervals, and retains correction
  as a new historical fact.
- **S03:** immutable employee qualifications, certificates and licences, with
  expiry derived from dates and revocation/supersession retained as immutable
  lifecycle evidence. Qualification, training and performance evidence uses
  DMS-owned, typed version links; no Workforce file store or parallel document
  model was introduced.
- **S04:** tenant/project/position-scoped training requirements; immutable
  attendance/completion records; optional performance evidence. Performance is
  sensitive and has no compensation, disciplinary, promotion, project-cost or
  financial effect.
- **S05:** immutable, effective-dated sensitive `LaborRateVersion` records.
  Version intervals are checked under lock. Rates are Workforce reference facts
  only: they do not create labor time, payroll, payable, project cost,
  accounting, Treasury, cash, commitment or forecast facts.

## Lifecycle, scope and evidence

Every new record is organization-scoped; related employee, catalogue, position
and optional project references must share the organization. Active catalogues
may be used for new facts; historical facts are immutable. Qualification status
is `valid`, `expired`, or `revoked/superseded` as derived from retained history.
The UI exposes a Persian-first Workforce workbench, employee-history panels and
an evidence-upload flow. The latter creates a DMS document/version and its
typed Workforce link atomically, subject to both DMS and Workforce access.

No P7 approval workflow was activated. Revocation is a separately permissioned,
reasoned event; an already-final Workforce fact is not edited or deleted.

## Permission and SoD boundary

| Capability | Permission codes | Default grant |
| --- | --- | --- |
| Skills and competencies | `workforce_skills.view/manage` | Tenant/company owner, tenant admin/manager, project/company/operations manager |
| Qualifications, training and revocation | `workforce_qualifications.view/manage/revoke` | Same management set; DMS upload/view remains separately required |
| Performance | `workforce_performance.view/manage` | None |
| Labor-rate versions | `workforce_labor_rates.view/manage` | None |

Sensitive performance and labor-rate permissions are removed from every default
role. They require an explicit organization-specific role grant. Access remains
tenant scoped; project-bound training actions also require applicable project
scope. A qualification, training result, performance record, skill, position or
project assignment never supplies an authorization grant. DMS evidence retains
its own confidentiality and document access checks.

## Explicitly excluded and still gated

This tranche does **not** implement or activate calendars, shifts, attendance,
leave, mission, overtime, timesheets, payroll rules/runs/results, tax,
employee-insurance lists, employee self-service, provider integration,
notifications, queues, project-cost consumption, AP/payroll payable,
accounting posting, Treasury or cash. It does not mutate P6 commercial,
contractual, entitlement, Billing, accounting or financial facts.

The following Product Owner/legal decisions are still required before a consumer
is authorized: labor-rate component semantics and source-of-truth; rounding,
currency, effective-date correction and approval authority; payroll/tax/
insurance jurisdiction, periods, schemas, retention and submission evidence;
attendance source hierarchy and exceptions; project-cost source contract and
classification; payable/posting/reconciliation/settlement authority; and maker-
checker, payroll-release and Treasury separation rules.

## Preserved unrelated issues

This tranche does not resolve the known 19 unregistered permission-registry
models, 12 permission-namespace mismatches, `MATERIAL_DOCUMENTS_LINK` gap, six
obsolete P6 assertions, or two serialized restore errors. They remain separate
remediation issues and are not represented as P7 authorization or entitlement.

## Historical handoff boundary

At this closeout the smallest safe next tranche was **P7-S06 calendar/shift
policy foundation only**: tenant calendar, holiday and shift definitions with no attendance
capture, no work-time calculation and no financial consumer. It requires Product
Owner decisions on calendar ownership, holiday source/override, shift taxonomy,
timezone and cross-midnight policy, archival/correction rules, and its
permission/default-grant matrix. P7-S07–S12 attendance through timesheets remain
separate authorization decisions.

## Historical proposal for P7-S06–S12

| Session | Exact proposed scope | Product Owner decisions required before authorization |
| --- | --- | --- |
| S06 | Tenant work calendars, holidays and shift definitions only; no attendance capture or calculation | Calendar owner, holiday source/override, timezone, cross-midnight/break policy, correction/archival, permissions |
| S07 | Site/project attendance fact, controlled manual capture and exception state only; no device/provider integration | Attendance source hierarchy, identity evidence, late/missing/duplicate policy, site scope and correction SoD |
| S08 | Leave and mission request/evidence lifecycle only | Categories, accrual/entitlement ownership, statutory retention, overlap/approval/return rules and delegated authority |
| S09 | Overtime request, review and approval evidence only | Jurisdiction, eligibility, caps, rate/compensatory-time semantics, maker-checker and payroll-consumer boundary |
| S10 | Attendance import contract and controlled correction/reconciliation workbench only; no live provider | File/device provider decision, idempotency key, source retention, error disposition, privacy and incident support ownership |
| S11 | Project/site/activity timesheet entry and immutable submitted history only | Allowed coding hierarchy, period/cutoff, attendance reconciliation, edit/correction rules, employee self-service decision and project scope |
| S12 | Timesheet review/approval and a non-posting labor-distribution preview only | Approval/SoD, rate-selection source, allocation/conservation/rounding, Project Cost source contract and explicit exclusion of payroll/AP/GL/Treasury/cash activation |

These rows record the proposal that preceded the later bounded authorization.
The delivered decisions and boundary are authoritative in the P7-S06–S12
implementation record. Payroll, tax, employee-insurance, statutory submission,
payable, posting and settlement remain outside S06–S12 and unauthorized.

## Validation record

- `manage.py check`: passed.
- `makemigrations --check --dry-run`: passed.
- Focused PostgreSQL test: `apps/workforce/test_p7_s01_s05_workforce_foundation.py`
  passed (3 tests) against an isolated database; the shared test database was not
  altered.
