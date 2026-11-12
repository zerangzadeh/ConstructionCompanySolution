# MVP scope reconciliation

Branch main at 865fa3f3f7868e81b0aafba05d2683b28fe33b1e, matching the local origin/main reference and Phase A baseline. At entry Git showed the Phase A validation folder as untracked and no tracked changes. Current registry and MVP setting agree with Phase A on all 23 Platform Admin routes. The isolated browser process explicitly pins MVP. The inventory and Phase A execution matrix are preserved.

| Disposition | Rows |
|---|---:|
| Original Phase A execution rows | 1127 |
| Added shared tenant selector step | 1 |
| Active MVP | 793 |
| Conditional MVP | 69 |
| Representative protection only | 1 |
| OUT_OF_SCOPE_MVP | 265 |
| Later-wave active rows | 756 |
| Wave 01-A | 41 |
| Wave 01-B | 66 |

The MVP functional/UI denominator is 862 rows across 41 catalog scenarios and 11 batches. Conditional rows need eligible state and explicit authority. CV-GUARD-01 contributes one separate representative HTTP denial check for technical Django Admin and three deferred MVP ESS source variants. The generic mixed-source route and the rest of the historical hidden-route checks are excluded from the active plan. Hidden apps remain backend-active.

Wave 01 retains the 39 selected B01 and 66 B10 Phase A rows, adds the shared tenant-selection row to UAT-01, and adds the single existing guard row as a security-only control. UAT-15 keeps cross-module permission probes as scoped denial checks, with business transitions and full module journeys left to their assigned batches. Deferred rows remain NOT_RUN. Use the CSV's separate dimension columns and evidence pointers. An excluded row can never count as PASS.

## Product Owner scope decision recorded 2026-11-12

The explicit Project Dashboard redesign request, section 10, is the authority for decision `PO-B02-PROJECT-DASHBOARD-20261112`. The [decision overlay](execution/B02_PO_SCOPE_DISPOSITIONS.csv) applies after the historical execution matrix and B02 remediation retest. Both earlier CSVs retain their original results and evidence.

- Worker archive, worker image viewing and worker image upload are `OUT_OF_SCOPE_MVP` at the UI and acceptance level. Their three whole execution rows are excluded from the current acceptance denominator. This decision subtracts three rows from the historical 862-row MVP denominator, yielding 859 for this decision alone.
- Reservation-backed leave submission and review are `OUT_OF_SCOPE_MVP` for the complete operational MVP acceptance journey. Each shares a matrix row with Mission, so only the leave branch is excluded. Mission and its previously verified submission and independent review remain in scope. These two whole rows are retained in the denominator.
- Current Projects List design is Product Owner accepted and must be preserved. Project Detail has an approved redesign direction, with final visual acceptance pending. See the [design registry](APPROVED_DESIGN_CONFORMANCE_REGISTRY.md#projects-design-decisions-recorded-2026-11-12).

Scope exclusion never becomes a test PASS or blanket B02 acceptance. Existing models, services, protected routes, reservation contracts and data are preserved. This decision records no new exposure, permission, schema or production authority. The [redesign report](execution/B02_PROJECT_DASHBOARD_REDESIGN_REPORT.md) records implementation and review readiness separately.
