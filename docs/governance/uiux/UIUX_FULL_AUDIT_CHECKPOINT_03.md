# BONIRA UI/UX Full Audit Checkpoint 03

## Baseline

`main @ 43ac319c6e73e48ca9626461b73987922c498ec3`

## Progress

- Static screen candidates: **383**
- Static-reviewed routed surfaces: **60**
- Findings: **64**
- HIGH: **44**
- MEDIUM: **20**
- CRITICAL: **0**
- Root patterns: **19**
- Positive internal reference patterns: **7**
- Findings requiring domain review: **0**

No remediation has been authorized or executed.

## Cross-cutting form audit expansion

The Product Owner requirement regarding cascade filtering, re-use of known data and selection instead of re-entry is now formally active as the audit lens:

`Form Intelligence & Data Reuse`

Each material form will be evaluated to classify user-visible fields as:

- USER_DECISION
- SELECT_EXISTING_DATA
- CASCADE_FILTERED
- SYSTEM_DERIVED
- CONTEXT_DEFAULTED
- READ_ONLY_INFORMATION
- ADVANCED_SPECIALIST
- HIDDEN_TECHNICAL

The rule does not weaken server authority. Client-side narrowing/defaulting is a usability layer; authorization, tenant isolation and relationship validation remain mandatory server-side.

## New systemic findings

### Cascade filtering is inconsistent across BONIRA

Examples confirmed at the frozen baseline:

- Daily Report loads all organization Projects, Sites and active Phases; Project/Site/Phase mismatch is discovered only in form validation.
- Equipment Assignment and Maintenance load all organization Sites and reject an incompatible Project/Site combination after submit.
- Payroll Employment Configuration and Rule forms load Projects and Sites independently.
- Procurement Purchase Order loads all approved organization Purchase Requests independently of the selected Project and rejects mismatches in `clean()`.

This is now:

`RP-C18-CASCADE-FILTERING-INCONSISTENT`

### Users are repeatedly asked for values the system can derive

Examples include:

- Daily Report material entry asks for Material plus material name/UOM/unit even though selecting Material determines those values.
- Payroll forms ask for JSON snapshots, source version/status and idempotency keys.
- Supplier Portal asks the supplier for SHA-256 integrity metadata.
- Equipment meter/usage/fuel forms ask operators for source keys.

This is now:

`RP-C19-DERIVABLE-DATA-REENTRY`

### BONIRA already contains a better implementation

`ExpenseForm` is recorded as `REF-P07-EXPENSE-CONTEXT_CASCADE`.

It already demonstrates the desired direction:

- membership-scoped projects;
- active-project defaulting;
- phase narrowing by selected project;
- an options endpoint for cascade refresh;
- server-side relationship validation retained.

The remediation program should reuse this capability rather than invent a second cascade mechanism.

## Other findings in this checkpoint

- Accounting reconciliation still exposes hashes, UUIDs and internal exception codes.
- Treasury movement detail exposes raw movement/journal IDs.
- Compliance detail presents raw lifecycle/state-machine language.
- Knowledge candidate forms bypass the shared form component pattern.
- Support case evidence shows full SHA-256 values in the ordinary user view.

## Audit boundary

The following transformation is valid UI remediation:

`Project selected → Site list narrows → canonical Site ID submitted → server validates access and project relationship`

The following is not authorized by the UI/UX audit:

`change the underlying Project/Site ownership, permission semantics or domain relationship to make the UI easier`.

## Next batch

Continue static audit across:

- remaining Accounting statements/journal/opening forms;
- Treasury statement/operational forms;
- Billing statutory and payable flows;
- Payroll run/statutory/handoff detail;
- Workforce foundation and structural forms;
- Equipment work-order/cost forms;
- Commercial tender forms;
- Knowledge publication and promotion;
- Support privileged-access lifecycle;
- shared pagination/date/status/filter/form components.

After these batches, build the first near-complete impacted-surface map before drafting remediation packages.
