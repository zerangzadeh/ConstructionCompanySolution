# P7-S23–S28 Statutory Payroll Tax and Employee Insurance Implementation

**Status:** Product Owner accepted (2026-10-04)  
**Status date:** 2026-10-04  
**Prerequisite:** P7-S01–S22 Product Owner accepted  
**Next boundary:** P7-S33–S36 subsequently Product Owner accepted, consolidating
P7-S01–S36 as complete within documented non-production boundaries; P8 remains
planning-only and production activation remains unauthorized

**Acceptance record:** Product Owner accepted this bounded framework based on
the completed implementation, focused PostgreSQL statutory validation and Core
Payroll regression validation. Acceptance preserves all fail-closed behavior and
does not authorize statutory values or interpretations, official schemas or
identifiers without verified authority, calendar/deadline rules, provider
behavior, credentials, live transmission, automatic filing, notifications,
schedulers, queues, liabilities, Accounting/GL, Treasury/cash, Project Cost or
production activation.

## 1. Bounded outcome

P7-S23–S28 extends finalized Core Payroll with a fail-closed statutory framework
for Payroll Tax and employee social insurance. It implements Platform-owned,
effective-dated authority; deterministic Decimal calculations; official-schema
output generation; versioned employer/workshop/employee identity evidence;
correction/replacement lineage; immutable provider-neutral export/status/error
evidence; human retry resolution; and calculation-to-output reconciliation.

No Iranian rate, bracket, exemption, threshold, cap, minimum wage, contribution
share, identifier, calendar conversion, schema, deadline, rounding rule or
provider behavior is seeded or inferred. Until a Platform Admin publishes a
source-backed and accepted-review-backed version, the corresponding calculation
or output is unavailable.

## 2. Regulatory ownership and lifecycle

The existing `PlatformPolicy` / `PlatformPolicyVersion` authority is reused; no
parallel regulatory system exists. Four code-owned, Tenant-nonselectable policy
families define the available contracts:

- `payroll-tax-regulatory`;
- `employee-insurance-regulatory`;
- `payroll-tax-output-schema`;
- `employee-insurance-output-schema`.

Platform Admin may create, review and publish the same version. Publication still
requires external-authority source linkage and accepted review evidence. Runtime
resolves the newest published effective version directly by Payroll period end;
historical calculations and outputs pin the exact policy/version, parameters,
source identifiers and snapshots. Published history remains immutable and a
Tenant cannot select or override a national version.

## 3. Data ownership and immutable lineage

Payroll owns the following new evidence:

- `StatutoryCalculation`, `StatutoryEmployeeResult` and
  `StatutoryCalculationLine` pin the finalized Payroll run, policy version,
  source/result digests, component mapping, monetary snapshot and exact results;
- `StatutoryReviewEvidence` records an append-only accepted/rejected review;
- `StatutoryIdentityEvidence` records versioned, effective employer/workshop or
  employee identifiers only for keys explicitly allowed by the effective official
  schema; values remain Tenant-scoped and never appear on general Workforce or
  Project screens;
- `StatutoryOutput` pins schema version, schema/identity evidence, payload,
  digest, output identity and original/correction/cancellation series;
- `StatutoryExportEvidence` records immutable artifacts, idempotency and
  correlation keys, attempt/retry lineage and manual/provider-neutral outcomes;
- `StatutorySubmissionResolution` retains append-only human resolution; and
- `StatutoryReconciliation` proves calculation/output totals or retains a
  difference as an exception.

Corrections require a finalized successor/replacement Payroll run and create a
new linked statutory calculation/output revision. Finalized Core Payroll,
attendance, time, Workforce and P6 facts are never changed.

Migrations:

- `payroll.0003_p7_s23_s28_statutory_payroll`;
- `organizations.0093_p7_s23_s28_statutory_payroll_permissions`;
- `payroll.0004_p7_s27_statutory_identity_evidence`.

## 4. Payroll Tax behavior

The reviewed Platform version must explicitly provide complete component
classification/mapping, basis factors, period/cumulative basis, exemptions,
brackets, floor/ceiling, line-rounding method/scale and successor-only correction
behavior. Every finalized Payroll result component must be mapped. Gaps,
overlapping/invalid tiers, uncovered basis, unsupported cumulative behavior,
invalid Decimal values or missing authority stop the transaction.

The implemented period calculation subtracts explicit exemptions, applies
explicit floors/ceilings, evaluates contiguous progressive brackets, rounds only
at the configured line boundary and stores unrounded plus rounded lineage.
Cumulative calculation deliberately remains unavailable until authoritative
opening/cumulative treatment is supplied.

## 5. Employee insurance behavior

Employee insurance is an independent Payroll consumer and does not import P6
contractor-insurance or Article 38 logic. Its reviewed Platform version must
explicitly provide component classifications, contribution categories and payer
(employee/employer/other), wage or wage-and-day basis, floors/ceilings,
exemptions, rounding and correction behavior. Wage-and-day mode requires one
explicit finalized Payroll quantity as work-day evidence; absence or ambiguity
fails closed. Each contribution category retains its exact basis, rate,
unrounded amount, rounded amount and payer.

## 6. Official outputs and identity evidence

Tax and insurance outputs resolve separate effective official-schema versions.
The schema must explicitly supply its identifier, required official identifier
keys, calendar mapping, monetary scale, field mapping, required fields and
encoding. Only `gregorian_iso` date mapping is currently supported; any other
official calendar mode remains gated until its authoritative conversion contract
and implementation are approved. Monetary serialization refuses precision loss.

Employer/workshop and employee identity evidence is accepted only when the exact
key is named by the reviewed schema. Output generation pins the evidence IDs and
fails closed for missing, duplicate-scope or ineffective identity evidence. The
generated payload and digest are immutable. No live provider transport occurs.

## 7. Export, status, retry and reconciliation

An export attempt stores the exact payload artifact snapshot and SHA-256 digest,
unique Tenant idempotency/correlation keys, attempt number, optional predecessor,
manual/provider-neutral status, provider reference and rejection/error evidence.
The same idempotency key replays the original evidence. A retry requires an
append-only human `retry_authorized` resolution and locks the output while the
next attempt is allocated. Output creation also records an immutable total
reconciliation against its statutory calculation.

No credentials, network adapter, automatic filing, scheduler, queue or
notification infrastructure is present.

## 8. Privacy, permissions and UI

Seven new permissions are registered and receive no default-role grants:

- `payroll_statutory_configuration.view`;
- `payroll_statutory.prepare`;
- `payroll_statutory.review`;
- `payroll_statutory_outputs.generate`;
- `payroll_statutory_outputs.export`;
- `payroll_statutory.correct`;
- `payroll_statutory_audit.view`.

General Payroll, Workforce, Accounting or Tenant-management access grants none of
them. Services re-check active membership, Tenant scope and permission inside
transactions. The Persian-first RTL UI provides Platform-version visibility,
calculation/review, statutory identity capture, output/history, correction
lineage, export/error evidence, human resolution and reconciliation without
exposing this data in general Workforce or Project screens.

## 9. Validation record

Focused PostgreSQL validation covers effective authority resolution, mandatory
source/review evidence, Tenant non-selection, historical policy pinning, complete
tax/insurance component mapping, independent contributions, Decimal rounding,
schema and identity pinning, both output families, original/correction lineage,
missing-authority/schema failure, permission denial, Tenant isolation,
idempotent replay, a real two-thread export race, immutable history,
reconciliation, RTL UI and explicit absence of journal, AP obligation, Treasury
movement and Project Cost facts.

Validation completed on PostgreSQL:

- the focused statutory module passed on a newly created test schema (`7 passed`)
  and again after final fixture closeout with the reused schema (`7 passed`);
- the real two-thread idempotency race passed independently (`1 passed`);
- the P7-S13–S22 Core Payroll regression module passed (`14 passed`);
- `manage.py check`, `makemigrations --check --dry-run`, targeted Ruff checks and
  `git diff --check` passed. The diff check reported only existing Windows line-
  ending normalization warnings.

The focused module is
`apps/payroll/test_p7_s23_s28_statutory_payroll.py`.

## 10. Unresolved gates

The following remain unavailable until separately evidenced and approved:

- every real Iranian tax/insurance value and interpretation;
- cumulative/opening tax treatment and unsupported employee cases;
- official tax and employee-insurance schema/identifier/calendar/file contracts;
- authoritative Jalali or other official calendar conversion;
- official employer/workshop and employee identifier semantics;
- filing deadlines, retention requirements and provider outcome semantics;
- credentials, provider adapters, live submission, automatic filing and
  production activation.

The pre-existing 19 unregistered models, 12 permission namespace mismatches,
`MATERIAL_DOCUMENTS_LINK` enforcement-reference gap, six obsolete P6 assertions
and two serialized test-database restore errors remain separate and unchanged.

## 11. Historical P7-S29–S32 planning record

P7-S29–S32 was subsequently Product Owner accepted on 2026-10-04 under the
bounded proposal-only implementation recorded in
`P7_S29_S32_FINANCIAL_HANDOFF_IMPLEMENTATION.md`; P7-S33–S36 is subsequently
Product Owner accepted under its final assurance/closeout packet.
The following is the pre-authorization planning record, retained for decision
lineage:

| Session | Proposed bounded scope | Product Owner decisions required before authorization |
| --- | --- | --- |
| P7-S29 | Payroll liability handoff | Approve liability owner/source contract, employee/employer/tax/insurance account mapping authority, recognition date, currency/rounding, aggregation grain, idempotency, correction/reversal treatment, AP/subledger boundary and whether creation is explicit or automatic. |
| P7-S30 | Accounting posting | Approve journal producer contract, debit/credit mapping versions, posting date/period controls, dimensions/cost centers, maker-checker, batch identity, reversal/replacement behavior, reconciliation and exact failure semantics. Accounting must remain sole journal authority. |
| P7-S31 | Treasury payment | Approve payment-request ownership, payee/bank identity custody, net-pay and authority-payment separation, approval/release SoD, partial/retry/reject/cancel behavior, settlement allocation, provider/bank boundary and cash-date reconciliation. Treasury must remain sole cash authority. |
| P7-S32 | Project Cost distribution and closeout | Approve which finalized Payroll components become actual labor cost, employee/employer/statutory inclusion, timesheet/project/site/activity allocation source, unallocated/rounding treatment, correction reversal, conserved totals, source-contract versioning and cross-domain reconciliation/acceptance gates. |

The package also needs an explicit decision on whether P7-S29–S32 may proceed
with statutory calculations still fail-closed/unactivated, or requires approved
real statutory versions first. Authorization must state which producers activate,
whether activation is pilot-only, and the required financial/security sign-off.
