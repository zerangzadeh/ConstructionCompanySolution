# BONIRA UI/UX Full Audit Checkpoint 06

## Baseline

`main @ 43ac319c6e73e48ca9626461b73987922c498ec3`

## Progress

- Static screen candidates: **383**
- Static-reviewed routed surfaces: **78**
- Findings: **89**
- HIGH: **65**
- MEDIUM: **24**
- CRITICAL: **0**
- Root patterns: **23**
- Positive internal reference patterns: **12**
- Findings requiring domain review: **0**

No remediation has been authorized or executed.

## Major conclusions in this checkpoint

### Jalali input is not consistently enforced

The canonical `JalaliDateMixin` exists and is used by modules such as Accounting, Procurement, Equipment and Compliance. Billing commercial/statutory forms, however, define multiple native browser date inputs while subclassing plain `forms.Form`.

This is now recorded as:

`RP-C23-JALALI-INPUT-INCONSISTENCY`

The remediation is presentation/input normalization only. Stored dates remain canonical Gregorian values.

### Shared pagination can lose active filter/sort state

`bounded_table_pagination.html` builds navigation links using only `?page=N`.

By contrast, the shared sort helper deliberately copies the existing query string and changes only sort/direction/page state.

The pagination component should follow the same query-preserving rule.

This is now:

`RP-C24-PAGINATION-QUERY-STATE-LOSS`

### Cascade filtering continues to be the correct systemic target

New examples:

- Compliance Project → Site;
- Equipment Employee → Qualification;
- Equipment Work Order → eligible spare transactions;
- Treasury origin Payment Request → movement project/context.

These findings strengthen the decision to solve dependent selection through shared form intelligence rather than page-specific validation messages.

## Positive internal patterns

Two more BONIRA patterns are now preserved as references:

`REF-P11-EMPLOYEE-KNOWN_DATA_REUSE`
- selecting an existing account hides/disables duplicated personal fields;
- the UI explicitly explains that known data need not be re-entered.

`REF-P12-WORKFORCE-PROJECT_SITE_CASCADE`
- Project selection dynamically fetches Site choices;
- Site stays disabled before the parent selection;
- loading/error/precondition states are handled;
- server-side filtering remains authoritative.

These directly support the Product Owner's requirement for known-data reuse and cascade filtering.

## Next static-audit batch

Continue with:

- shared status/status-color semantics;
- date/display consistency on list/detail pages;
- remaining Accounting statement/period pages;
- Treasury account/posting selectors;
- Billing payable and statutory evidence flows;
- Workforce team/position/structure pages;
- Equipment cost and maintenance selectors;
- Knowledge promotion/publication lifecycle;
- remaining search/filter/pagination/table interaction patterns.

The next major milestone is the **Static Audit Coverage Review**, after which the Runtime/Role Validation Matrix can be generated without starting remediation prematurely.
