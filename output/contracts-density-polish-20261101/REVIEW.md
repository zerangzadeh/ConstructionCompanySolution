# Contracts List — remaining visual refinements

Date: 2026-11-01, Asia/Tehran.

```text
REFERENCE VISUAL CONFORMANCE: PASS
PRODUCT OWNER VISUAL ACCEPTANCE: READY FOR REVIEW
```

Only Contracts-scoped CSS and its stylesheet cache version changed. No template
structure, JavaScript, backend/query logic, filter semantics, Domain, Model,
Migration, Permission, tenant/project Scope, Workflow, Sidebar, Application Shell
or Product Surface change. Existing uncommitted work was preserved.

| Requested refinement | Verified result |
| --- | --- |
| Advanced Filters | Desktop panel 139.1px; inputs 32px; both actions exactly 32px. Reduced heading/label/field/action spacing. Mobile panel 289.1px, inputs 38px, actions aligned at 36px. |
| Summary Toolbar | Compact 52px desktop toolbar; clearer count/value hierarchy, aligned baselines and restrained separator. No card or additional large surface. Existing count, exact amount and currency preserved. |
| Quick Filters | All controls on one row at 1440px and 1672px. Project control approximately 253px at 1672px; full-width controls on mobile. Existing fields and interactions unchanged. |
| Table Header | Approximately 40.2px, font weight 500, lighter text and tighter spacing. Side, status and date headers align with their cells on desktop. Sort indicators remain limited to the five existing sortable columns. |

Real connected-Chrome screenshots were inspected against the supplied visual
reference and the preceding Contracts output. The requested compact refinements
retain that composition without a new design or fabricated controls/data:

- [Desktop, Advanced Filters open](desktop-advanced.jpg).
- [Mobile, Advanced Filters open](mobile-advanced.jpg).
- [Mobile, Summary and results](mobile-summary.jpg).
- [Desktop measurements](desktop-checks.json), [small-mobile overflow check](small-mobile-checks.json).

Manual checks: desktop 1672/1440px and mobile 390/320px; no page overflow. Advanced
Apply retained the existing search/project filters and returned one matching
contract. Advanced Clear returned the twenty general results and their existing
sum. Native Enter toggled the advanced panel closed/open. Mobile quick filters
opened/closed with full-width controls. The first-row secondary menu remained
inside the table boundary after reducing the header height.

Django system check: no issues. `git diff --check`: PASS. No broad audit or new
test suite was introduced for this CSS-only change.

[Exact two-file change](CHANGES.patch); [entry snapshots](baseline/).
Branch `main`; HEAD `5b760e853b329e2b03415da7b046641359db6a62` unchanged.
No business-data mutation, staging, commit, push or production action. Ready for
Product Owner review; Human visual acceptance has not been issued.
