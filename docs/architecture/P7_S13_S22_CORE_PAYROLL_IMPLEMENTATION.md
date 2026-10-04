# P7-S13–S22 Core Payroll Implementation Packet

**Status:** Product Owner accepted (2026-10-04)

**Date:** 2026-10-04

**Authorization:** the bounded Product Owner instruction for P7-S13–S22 only
**Acceptance:** includes the locked-run resolution and pinning of the authoritative
versioned `accounting-money-precision` and `accounting-rounding` policies. Final
rounding uses the pinned policy; Payroll has no universal `0.01` monetary quantum.
**Next sessions:** P7-S23–S28 are subsequently Product Owner accepted under their
bounded authorization and recorded in
`P7_S23_S28_STATUTORY_PAYROLL_INSURANCE_IMPLEMENTATION.md`; P7-S29–S32 and
P7-S33–S36 are subsequently Product Owner accepted, consolidating P7-S01–S36 as
complete within documented non-production boundaries. P8 remains planning-only and
production activation remains unauthorized.

## 1. Session contract and outcome

This tranche implements a Payroll-owned, multi-tenant Core Payroll domain without
creating a parallel Workforce, Timekeeping, Accounting, Treasury or Project Cost
authority. The vertical slice includes effective employment/pay configuration,
typed components, versioned bounded rules, explicit periods and runs, immutable
input snapshots, deterministic Decimal calculation, result lineage, review and
finalization, restricted payslips, adjustments/arrears/off-cycle runs, and
reversal/replacement history.

The implementation stop condition was satisfied by the focused PostgreSQL tests,
clean-schema migration validation, Django check, migration-drift check, targeted
Ruff and whitespace checks. Product Owner accepted this bounded scope on
2026-10-04; acceptance does not authorize a later P7 session or consumer.

## 2. Ownership and integration boundary

| Authority | P7-S13–S22 behavior |
| --- | --- |
| Payroll | Owns pay configurations, components/rules, periods/runs, explicit inputs and snapshots, results/lines/exceptions, payslips, adjustments and reversal/replacement lineage |
| Workforce | Remains the employee identity and workforce-master authority; Payroll references `Employee` and never duplicates it |
| Timekeeping | Remains the attendance/timesheet authority; Payroll accepts only explicit approved/final source references and copies their payload/version into an immutable snapshot |
| Accounting | Remains the only journal/GL authority; Payroll creates no journal or ledger balance |
| Treasury | Remains the payment/cash authority; a payslip is not payment evidence |
| Project Controls | Remains the project-cost authority; Payroll creates no actual-cost fact |

No automatic cross-domain producer is active. `PayrollRun` retains a stable future
handoff identity, but P7-S29–S32 must separately authorize and specify every
liability, posting, payment and Project Cost consumer.

## 3. Models and migrations

`apps/payroll/migrations/0001_initial.py` creates:

- `EmploymentPayConfiguration`: effective employee pay model/rate version with
  predecessor, optional project/site scope, evidence and active-range exclusion;
- `PayrollComponent` and `PayrollRule`: typed catalogue and effective bounded
  calculation versions; statutory-reserved rules cannot activate in Core Payroll;
- `PayrollPeriod` and `PayrollRun`: explicit boundaries/cutoff, lifecycle,
  idempotency and correction/reversal/replacement links;
- `PayrollInput` and immutable `PayrollInputSnapshot`: explicit approved/final
  source facts with source/version/payload and canonical digest;
- `PayrollRunEmployee`, immutable `PayrollResultLine`, and `PayrollException`:
  employee totals, component-level explanation and fail-closed exceptions;
- immutable `Payslip`, `PayrollAdjustment`, and `PayrollReversal` evidence.

PostgreSQL exclusion constraints reject overlapping active employee pay versions,
active component-rule versions and open/locked/finalized periods. Unique keys guard
run creation, regular-run allocation, snapshots, payslips and reversal retries.
`apps/organizations/migrations/0092_p7_s13_s22_core_payroll_permissions.py`
registers the Payroll catalogue with no built-in role grants.

`apps/payroll/migrations/0002_pinned_monetary_policy.py` adds the immutable
precision-policy link, rounding-policy link and complete policy snapshot to each
locked Payroll run. The shared policy catalogue permits only money scales `0` and
`2`; current IRR v1 remains scale `0`.

## 4. Lifecycle and locking

```text
Pay configuration/rule: draft -> active -> retired (new version for change)
Period:                open -> locked -> finalized
Run: draft -> inputs_locked -> calculated -> in_review -> approved -> finalized
                                        \-> exception (controlled correction only)
Finalized run: finalized -> reversed -> linked reversal + optional replacement draft
```

Services re-read and lock the run, period and employee results inside
`transaction.atomic()`. Preflight requires one effective pay configuration and all
required explicit variable inputs. Missing configuration/input, no applicable rule,
unresolved statutory authority, open error exception or negative ordinary net pay
fails closed. A failed preflight retains an explicit exception without locking the
run. Successful locking creates immutable snapshots first and then records the run
digest atomically.

Finalized runs/results/lines/payslips and retained snapshots are not edited or
deleted. Arrears, retroactivity, opening facts and off-cycle corrections are
explicit adjustment records in a new run. Reversal creates a finalized negative
mirror with source-line references; replacement is a linked draft and never
rewrites the predecessor.

## 5. Deterministic calculation

Only three bounded operations are available: fixed amount, quantity multiplied by
an explicit rule/employment rate, and percentage of a prior component. There is no
tenant-authored Python, SQL, expression language, template or callback.

All values use `Decimal`. Quantity, rate, percentage, basis and unrounded component
results retain eight decimal places. At input lock, Payroll resolves the shared,
versioned Tenant `accounting-money-precision` and `accounting-rounding` policies
for the Payroll consumer, then pins both version links and a complete monetary-policy
snapshot on the run. Each component result and aggregate is rounded once at its
final monetary boundary using that pinned money scale and `ROUND_HALF_UP`; `0.01`
is therefore used only when the pinned currency policy has scale `2`, while scale
`0` uses quantum `1`. A later Tenant policy selection cannot reinterpret a locked,
calculated, finalized or reversed run. Each line retains component/rule identity and
version, employment version, snapshot/digest, source reference/version, basis,
quantity, rate, unrounded value, rounded result and applied-policy explanation. The
run calculation digest covers the locked input digest and result-line evidence.

Ordinary gross includes configured earning and allowance components;
reimbursements add to net without becoming gross; deductions reduce net; employer
and informational components do not change employee net. Negative ordinary net is
an error exception and cannot progress through ordinary finalization. No debt
recovery behavior is inferred.

## 6. Privacy, permissions and approval policy

The following permissions are separate and default-denied:

- `payroll_configuration.view` / `payroll_configuration.manage`;
- `payroll.prepare`, `payroll.review`, `payroll.finalize`, `payroll.adjust`;
- `payroll_results.view`;
- `payslips.view` / `payslips.export`;
- `payroll_audit.view`.

Every service checks active membership, Tenant status, permission and project/site
scope where the object carries that context. Employee position, qualification,
Workforce/timekeeping access and earlier lifecycle participation grant nothing.
General audit views exclude `payroll.*` events unless the viewer also has the
Payroll-audit permission.

Preparation, review and finalization are distinct capabilities. A single user may
perform all steps when explicitly granted all of them; no actor-inequality rule is
applied. This is an intentional Payroll-only policy for small Tenants and does not
change maker-checker rules elsewhere. Every transition remains separately checked
and audited inside the transaction.

## 7. Persian-first restricted UI and UAT handoff

Primary route: `/payroll/`; menu: **مالی و گزارش‌ها → حقوق و دستمزد**. The workbench
requires `payroll_results.view`. Configuration, run actions, results, payslips,
export and audit history each apply their dedicated permission at the HTTP and
service boundaries.

Delivered pages cover configuration/rules, periods/runs, explicit inputs,
calculation/review/finalization, exceptions, results/lineage, adjustments,
reversal/replacement, payslips and Payroll audit history. Templates inherit the
Persian `lang="fa"`, RTL shell, Rial labelling and Jalali display filters. The
payslip is a restricted finalized-result presentation; controlled JSON export
records its immutable content digest and an audit event.

UAT prerequisites: active Tenant, employee, explicit Payroll role grants, active
pay configuration and at least one active non-statutory rule. Happy path: create
period/run, add required approved/final inputs, lock, calculate, submit, approve,
finalize and view the payslip. Denied path: a Workforce-only member receives 403;
missing variable input creates a visible exception; negative net cannot submit.
Reversal warns that the original remains immutable and produces linked history.

Defect report: session ID; actor; Tenant/project/site; run/employee; steps; expected
result; actual result; permission set; exception code; correlation ID.

## 8. Validation evidence

- Follow-up monetary-precision verification: `16 passed` across the 14 Payroll
  cases and two shared monetary-policy calculation cases. It covers policy-driven
  scale `0`/`2` rounding and historical policy-version reproducibility.
- Focused PostgreSQL baseline before this follow-up: `13 passed` in
  `apps/payroll/test_p7_s13_s22_core_payroll.py`, covering effective versions,
  overlaps, snapshots, Decimal/rounding/lineage, missing-input failure, permissions,
  Tenant isolation, registry completeness and default denial, payroll-audit privacy,
  same-user multi-role completion, immutability, adjustment, reversal/replacement,
  negative net, retry/idempotency, real two-thread run creation, audit rollback,
  locked-snapshot independence from later catalogue changes, RTL UI and absence
  of Accounting/AP/Treasury/Project Cost effects.
- Django system check: passed.
- Migration drift: no changes detected.
- Targeted Ruff: passed.
- Clean PostgreSQL test-database rebuild plus the prior focused module: `13 passed`
  in 371.14 seconds before the bounded `0002_pinned_monetary_policy` follow-up.
  This follow-up intentionally used only the Product Owner-requested focused
  checks; migration drift is clean and the affected test database applied `0002`.
- Final whitespace check: passed.

The existing repository-wide register remains separate: 19 unregistered managed
models, 12 permission namespace mismatches, the `MATERIAL_DOCUMENTS_LINK`
enforcement-reference gap, six obsolete P6 assertions and two serialized
test-database restore errors are neither absorbed nor represented as Core Payroll
defects.

## 9. Preserved gates

P7-S13–S22 contains no Iranian tax rate/bracket/exemption, employee/employer social
insurance rate/cap, minimum wage, statutory allowance, overtime formula, legal
contribution rule, official schema or statutory rounding rule. It also creates no
AP/payroll liability, subledger balance, journal/GL entry, Treasury/payment/cash
record, Project Cost actual, employee self-service, notification, queue/scheduler,
live provider credential/transport or production activation.

## 10. Historical P7-S23+ handoff (superseded for S23–S28)

At this packet's acceptance date P7-S23+ was not authorized. The later bounded
P7-S23–S28 authorization, implementation and Product Owner acceptance packet
supersedes this status for those sessions only. The following remains the
historical decision handoff and grants no P7-S29+ authority:
implementation authority for statutory, accounting, Treasury, payment, Project
Cost, provider, self-service, notification, scheduler, queue or production work.

| Session | Proposed bounded outcome | Product Owner decision/evidence required before authorization |
| --- | --- | --- |
| P7-S23 | Statutory authority/version foundation and professional review evidence | Confirm Iranian launch jurisdiction and effective years; authoritative Tax/Labor/Social Security sources; named qualified reviewer/sign-off; rule publication/retirement and emergency correction policy; whether statutory approval requires a different person or may retain Core Payroll same-user multi-role behavior |
| P7-S24 | Payroll-tax calculation configuration and golden cases | Approve taxable/non-taxable component mapping; annual/monthly/cumulative basis; exemptions, brackets, caps/floors, rounding stage/precision, retroactivity and negative/correction treatment; supported employee/residency/multiple-employer cases; explicit unsupported cases that must fail closed |
| P7-S25 | Employee/employer social-insurance configuration and golden cases | Approve insurable/non-insurable component mapping; employee/employer/unemployment shares, ceilings/floors, day/wage basis, establishment/branch identifiers, exemptions/special categories, rounding and correction rules; explicit unsupported cases |
| P7-S26 | Version-pinned payroll-tax output/list generation and validation | Approve official schema/version, field semantics, IRR scale, calendar/year mapping, encoding/file naming, organization/employee identifiers, validation/error catalogue, totals/reconciliation and original/correction/cancellation lineage |
| P7-S27 | Version-pinned employee-insurance list generation and validation | Approve official list/disk schema/version, employer/workshop identity ownership, identity/day/wage fields, totals/reconciliation, correction/replacement lifecycle, encoding and legally required evidence/retention |
| P7-S28 | Provider-neutral submission package and immutable status/evidence | Decide evidence-only export versus approved test adapter; authorized submit/retry/resolve roles, credential custody boundary, idempotency keys, accepted/rejected/provider-error semantics, receipt/status evidence, retention/privacy/export, and whether live transport remains deferred to a later integration authorization |

Cross-session decisions must also cover YTD/opening balances without fabricated
historical runs, component mapping migration, official effective-date cutover,
golden cases supplied/approved by the professional reviewer, statutory audit
access/retention, and confirmation that P7-S23–S28 still creates no Accounting,
AP, Treasury, cash or Project Cost effect. P7-S29–S32 remains the only proposed
financial-activation tranche.
