# DEV-PAYROLL-YTD-BINDING-v2

Status: SYNTHETIC DEVELOPMENT-ONLY PAYROLL/YTD FIXTURE
Authority: DEV-SYNTHETIC-DATA-AUTH-20261020-V2

This document is not an organizational payroll policy, legal interpretation, tax rule, insurance rule, or Production configuration.

## Payroll year
- Code: DEV-PY-2026-A
- Version: 2
- Inclusive start: 2026-01-01
- Inclusive end: 2026-12-31
- Opening/YTD as-of: 2026-09-30
- Operational continuation boundary: 2026-10-01
- Currency: IRR

## Inclusion rule
- Include only rows where included_in_opening = YES.
- SUPERSEDED rows remain evidence only and must not contribute to opening totals.
- Replacement/correction lineage must be retained.
- Rows approved/finalized after 2026-09-30 are outside this opening fixture.

## Operational categories
Existing Decision-05 semantics remain authoritative:
- EARNING
- ALLOWANCE
- DEDUCTION
- REIMBURSEMENT
- EMPLOYER
- INFORMATIONAL remains non-monetary and is not represented here.

## Component handling
For each synthetic component code:
1. Resolve an existing Development component with the exact code if one exists.
2. Otherwise create a Development-only component through the existing canonical component service using the operational kind in the crosswalk.
3. Do not attach statutory/tax/insurance rates or Production legal meaning.

## Correction example
The source contains one SUPERSEDED overtime line and one replacement line.
Only the replacement is included in the opening amount; both records remain traceable.
