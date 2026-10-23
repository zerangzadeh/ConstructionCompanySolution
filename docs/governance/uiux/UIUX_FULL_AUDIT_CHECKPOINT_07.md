# BONIRA UI/UX Full Audit Checkpoint 07

## Baseline

`main @ 43ac319c6e73e48ca9626461b73987922c498ec3`

## Progress

- Static screen candidates: **383**
- Static-reviewed routed surfaces: **82**
- Findings: **95**
- HIGH: **70**
- MEDIUM: **25**
- CRITICAL: **0**
- Root patterns: **25**
- Positive internal reference patterns: **14**
- Findings requiring domain review: **0**

No remediation has been authorized or executed.

## Shared state semantics

The shared status badge has the correct five-family design intent, but the mapping coverage is incomplete. Safety and Quality pass lifecycle states such as `reported`, `assigned`, `action_in_progress`, `resolved`, `awaiting_verification`, `verified` and `closed`; most currently fall through to neutral.

This is now:

`RP-C25-STATUS-SEMANTICS-INCOMPLETE`

The fix is a shared presentation map, not a change to domain status values.

## Jalali display consistency

A second date problem is now distinct from the previously identified input-widget problem.

Accounting statement pages already demonstrate the correct output pattern with `jalali_date` / `jalali_datetime`. Other surfaces render raw Date/DateTime values directly, including Accounting periods, Safety, Quality and Billing payable certificates.

This is now:

`RP-C26-JALALI-DISPLAY-INCONSISTENCY`

Input consistency (`RP-C23`) and output/display consistency (`RP-C26`) are deliberately tracked separately.

## Accounting statements

The statement list/detail show both good and problematic patterns:

Good:
- Jalali reporting dates;
- consistent financial numeric formatting;
- detail drill-through from account lines.

Needs remediation:
- preview title renders raw `form.cleaned_data.kind`;
- preview rows render raw `line.account_type`;
- stored statement detail exposes scope/input/result hashes in the primary report area.

## Billing payable certificates

The payable certificate experience is operationally rich, but detail pages mix payment-certificate review with technical lineage including calculation versions, stable line identifiers and rate snapshots. These should remain available for auditability but not dominate the normal business view.

## Compliance template configuration

Inspection-template publication currently requires raw JSON entry for checklist, required evidence, outcome rules and source references. The canonical JSON can remain unchanged, but the user-facing editor should be structured/visual.

## Static-audit trajectory

The major systemic patterns are now stable enough that the next batch will focus less on discovering new root-pattern families and more on completing the affected-surface map.

Priority next coverage:

- remaining Billing payable/statutory surfaces;
- Treasury posting/account/reconciliation presentation;
- Workforce structure and development surfaces;
- Equipment cost/maintenance details;
- Knowledge publication/promotion lifecycle;
- remaining shared table/list/action conventions.

After that batch, prepare a **Static Audit Coverage Review** and the first `Runtime / Role-based Validation Matrix` without authorizing remediation.
