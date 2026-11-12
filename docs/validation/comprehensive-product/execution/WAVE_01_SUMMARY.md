# BONIRA Wave 01 execution summary

**2026-11-10 Asia/Tehran · MVP · main at `865fa3f3f7868e81b0aafba05d2683b28fe33b1e`**

| Scope | Planned | Evidence recorded | PASS | FAIL | BLOCKED | NOT_RUN | NEEDS_PO_REVIEW | PO_ACCEPTED |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Wave 01-A | 41 | 29 | 21 | 0 | 3 | 12 | 5 | 0 |
| Wave 01-B | 66 | 66 | 60 | 3 | 0 | 1 | 2 | 0 |
| Total | 107 | 95 | 81 | 3 | 3 | 13 | 7 | 0 |

Evidence recorded includes partially executed rows. One of the 13 NOT_RUN rows has partial policy catalog evidence. 12 rows were unattempted. The independent focused suite passed **75 tests and 60 subtests**. Actual Chrome and read-only persisted witnesses supplied the Wave 01 results.

**Fully validated within the scoped matrix** · PA-01 dashboard, PA-04 system users, PA-05 account lifecycle, PA-06 recovery, PA-07 Platform operators and PA-11 separation. UAT-01 and CV-AUTH-01 exercised the core user flows and retain approved design reference gaps. PA-02 and PA-03 likewise retain company visual reference gaps.

**Patterns checked** · Authentication and recovery, shared and Platform navigation, context and breadcrumbs, lists/tables, details, compact and sectioned forms, dashboard/workspace, confirmations and specialized Platform administration. See the [approved design registry](../APPROVED_DESIGN_CONFORMANCE_REGISTRY.md) and batch reports.

| Defect | Finding |
|---|---|
| BON-DEF-0001 · P2 | Platform member-role company selector exposes a redundant unnamed combobox to assistive technology. |
| BON-DEF-0002 · P2 | Platform audit date labels say Gregorian while the actual picker accepts Jalali. Canonical date conversion and the scoped result worked. |
| BON-DEF-0003 · P2 | A single click retires an active platform-wide protected-operation version without a confirmation step. History and audit persisted. |

**Business and authorization** · No failure confirmed in the executed assertions. Platform authority and explicit tenant delegation stayed separate. Three restricted requests need valid foreign records to prove the required object boundary.

**Historical findings** · F-015, F-016, F-017 and F-107 were reverified within the tested scope. No confirmed recurrence. Home hierarchy findings F-065 and F-066 were not independently adjudicated.

**Open work** · Resolve seven row-level reference decisions, complete the 12 unattempted and three blocked UAT-15 variants, and finish the policy catalog lifecycle row. Audit action and pagination remain supplemental browser coverage. The 756 later-wave rows remain deferred. The 265 excluded rows remain OUT_OF_SCOPE_MVP.

**Recommended next execution wave after Product Owner review** · Run B02 only, using its 68 derived rows for UAT-02, UAT-04 and CV-TIME-01. Start from a fresh isolated clone with project/site, workforce identity, calendar and independent review fixtures. Carry unresolved Wave 01 rows forward by their existing IDs for separate disposition.

[Authentication report](B01_AUTH_EXECUTION_REPORT.md) · [Platform Admin report](B10_PLATFORM_ADMIN_EXECUTION_REPORT.md) · [MVP matrix](../TEST_EXECUTION_MATRIX_MVP.csv) · [Scope reconciliation](../MVP_SCOPE_RECONCILIATION.md) · [Defect register](../DEFECT_REGISTER.md) · [Run environment and evidence](evidence/wave-01-865fa3f3/RUN_MANIFEST.md)
