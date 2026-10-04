# P7-S06–S12 Time and Attendance Implementation Record

**Status:** Product Owner accepted. This record covers only P7-S06–S12.
P7-S13–S22 was subsequently Product Owner accepted in
`P7_S13_S22_CORE_PAYROLL_IMPLEMENTATION.md`; P7-S23–S28 are subsequently Product
Owner accepted. P7-S29–S32 and P7-S33–S36 are subsequently Product Owner
accepted, consolidating P7-S01–S36 as complete within documented non-production
boundaries. P8 remains planning-only and production activation remains unauthorized.

## Product Owner acceptance

The Product Owner accepts the recorded P7-S06–S12 behavior and PostgreSQL
validation: tenant-timezone calendars, holidays, cross-midnight shifts and
explicit breaks; retained manual attendance/import/correction evidence and
exception handling; leave, mission and overtime review evidence; project/site/
activity timesheets; the retained attendance-versus-timesheet boundary;
minute-conserving labor-time preview evidence; and the documented permission,
scope, workflow/SoD, locking, audit and Persian-first RTL controls.

Acceptance preserves every no-effect boundary in this record. In particular, it
does not authorize or activate payroll, tax or social-insurance calculation,
statutory rules, monetary labor costing, automatic Project Cost, AP/AR,
Accounting, Treasury, cash/payment, live devices/providers, employee
self-service, production integrations, notifications, queues, schedulers or
production activation. The unresolved technical issues below remain separate
matters.

## Session outcomes

| Session | Delivered boundary |
| --- | --- |
| P7-S06 | Tenant-owned effective work calendars, reasoned holiday/working-day overrides, Tenant-timezone shift definitions, explicit cross-midnight flag and immutable explicit break periods. No statutory calendar is inferred. |
| P7-S07 | Tenant/project/site-scoped manual attendance presence records with draft/exception/final lifecycle, timezone-aware intervals, overlap detection, independent finalization and reasoned correction/reversal history. |
| P7-S08 | Leave and mission draft/submission/independent review evidence with overlap checks. Approval fails closed without an explicit approved-policy reference; no accrual or entitlement is calculated. |
| P7-S09 | Overtime request/submission/independent review evidence with overlap checks and the same policy gate. No eligibility, cap, multiplier, compensatory-time or payroll result is inferred. |
| P7-S10 | Provider-neutral normalized attendance-import contract with Tenant idempotency key plus content digest, immutable row outcomes, retained exceptions, reconciliation evidence and correction history. No adapter, credential, device or live provider connection exists. |
| P7-S11 | Employee-period timesheets with project/site/activity allocations, exact minute conservation, immutable submitted history and linked revision/supersession instead of editing finalized facts. |
| P7-S12 | Independent timesheet review evidence and immutable minute-only labor-distribution previews. Preview lines copy approved allocations and explicitly retain `RATE_AND_PROJECT_COST_POLICY_UNRESOLVED`; they cannot post or create a financial fact. |

## Ownership and lifecycle

The new `timekeeping` domain owns calendars, shifts, attendance facts and their
import/correction/reconciliation evidence, leave/mission/overtime requests,
timesheets and non-posting previews. Workforce continues to own `Employee`,
assignment, capability and reference labor-rate history. Projects continues to
own project/site/WBS/activity coding. DMS remains the sole document authority;
this tranche does not introduce a parallel blob or document link. Project
Controls remains the sole owner of Project Cost source contracts/facts and is not
called by Timekeeping.

Attendance states when a person was present. Timesheets state how approved time
was allocated. Neither service mutates the other. Final attendance uses a new
`AttendanceAdjustment` and optional replacement; submitted timesheets use a
linked higher revision. Request decisions, reviews, import rows, reconciliation
and previews are retained evidence. Application services lock the aggregate and
re-check permission, scope and maker-checker rules inside the transaction.

## Permissions, scope, SoD and default grants

New registered namespaces are `time_calendars`, `attendance`, `leave_mission`,
`overtime` and `timesheets`. They expose separate view, prepare/capture/import,
review, correction and preview permissions. Tenant Owner, Company Owner and
Tenant Admin receive the full set by default so Tenant administrators can
maintain calendars/import contracts. Tenant/Project/Company/Operations Managers
receive view, prepare and review but not calendar management, attendance import
or attendance correction. Supervisors receive view and preparation/capture;
Member and Viewer receive view only. Sensitive role customization remains
possible through the existing authorization authority.

Every service first resolves active Tenant membership and then intersects the
permission with organization/project/site scope. Cross-Tenant relationships and
cross-project sites/activities fail validation. Capturers cannot finalize their
own attendance; requesters cannot review their own leave/mission/overtime;
timesheet preparers/submitters cannot review their own sheet; attendance
correction requires distinct requester and approver who are also independent of
the original capture/finalization. Position, qualification, training, team and
Workforce assignment records are never permission grants.

## UI and operations

The Persian-first RTL `timekeeping` workbench is reachable from primary
navigation for `attendance.view`. It exposes permission-filtered calendar/shift
maintenance, manual capture, normalized import, attendance exception/finalization,
leave/mission and overtime request/review, timesheet allocation/submission/review,
and non-posting preview actions. All mutations are CSRF-protected POSTs or
validated forms and repeat the service-level checks. The UI labels policy gates
and the no-payroll/no-financial-effect boundary rather than implying an amount.

## Decisions applied

- `OrganizationSettings.timezone` is authoritative; a calendar cannot select a
  different zone. Timestamps are aware and work date is checked in that zone.
- A shift may cross midnight only when its flag and times agree. Every break is a
  separate retained interval wholly inside the shift; paid/unpaid is explicit
  configuration, not an inferred labor rule.
- Holidays/working overrides require a reason and optional source reference. No
  national holiday data is embedded.
- Import idempotency is `(organization, idempotency_key)` plus a canonical SHA-256
  content digest. Same key/same content returns the retained batch; same key with
  different content fails.
- Time allocation uses integer minutes and requires exact equality with the
  declared total. No rounding or money conversion exists.
- Leave/mission/overtime approval requires a nonblank policy reference. The
  reference is evidence only; the application does not interpret its law or
  payroll meaning.

## Explicit no-effect boundary

No operation creates or mutates Payroll, salary, entitlement/accrual balance,
Project Cost source contract/fact, Expense, AP/AR, payable, Accounting journal,
Treasury movement, cash, commitment, forecast, Billing, insurance, Article 38,
P6 commercial/contractual/claim/EOT facts or any other financial obligation.
Labor-rate selection, currency, multiplier and monetary preview remain disabled.
No employee self-service identity mapping and no live device/provider integration
is activated.

## Validation record

- Focused PostgreSQL service/UI suite: **7 passed** on the final reusable schema
  run. It covers timezone/cross-midnight/break behavior, tenant and explicit site
  scope, permissions/SoD, immutable correction history, leave/overtime overlap
  and policy gates, idempotent import exceptions, timesheet conservation/review,
  RTL reachability and unchanged Project Cost/GL/AP/Treasury/Payment counts.
- Clean disposable PostgreSQL schema recreation, migration apply through
  `timekeeping.0002`, test execution and disposal: **7 passed in 346.11s**.
- Focused permission-registry default check: **1 test / 11 role subtests passed**.
- `manage.py check`: passed with no issues.
- `makemigrations --check --dry-run`: no changes detected.
- Targeted Ruff: passed for Timekeeping and affected authorization/audit/config
  files.
- Targeted `git diff --check`: passed; line-ending conversion warnings only.

## Preserved unrelated issues

The pre-existing permission-registry/model and namespace gaps,
`MATERIAL_DOCUMENTS_LINK` issue, obsolete tests and serialized-restore failures
remain separate. This tranche does not use them as authorization and does not
claim to resolve them. DMS, Project Controls, P6 and P7-S01–S05 architecture was
checked; only current-state Timekeeping references required reconciliation.

## Historical proposed P7-S13 onward boundary and required decisions

This historical proposal is superseded by the accepted P7-S13–S22 implementation
packet. At the time, the smallest proposed next scope was **P7-S13 only: payroll policy and employment/pay input
contract design**, with no payroll calculation or run. It should define the
versioned policy owner, jurisdiction, employment/pay relationship, component
taxonomy, effective dates, source provenance, privacy classification and the
exact approved attendance/timesheet eligibility snapshot. Before authorization,
the Product Owner must decide:

1. supported employment/pay models and authoritative compensation source;
2. jurisdiction and professional/legal reviewer;
3. pay-period/cutoff/calendar ownership and retroactive-effective-date policy;
4. leave, mission and overtime entitlement/eligibility/cap semantics;
5. precision, unit, Rial/Toman/currency display and rounding authority;
6. rate/component selection, multiplier and compensatory-time semantics;
7. privacy roles, preparer/reviewer/release SoD and employee self-service posture;
8. exact correction, lock, reversal and retained snapshot rules;
9. whether approved attendance, approved timesheets or a governed reconciliation
   is the payroll input for each component;
10. retention/export and production activation/sign-off requirements.

P7-S14–S22 payroll calculation/run/result/lock/adjustment/reversal, P7-S23–S28
tax and employee-insurance outputs, P7-S29–S32 liability/payment/posting/Project
Cost distribution and P7-S33–S36 were subsequently delivered under their own
bounded packets. No roadmap status or this packet
authorizes them.
