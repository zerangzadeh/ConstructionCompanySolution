# P4-S31–S34 Project Controls Presentation Implementation Contract

**Authorized:** 2026-10-01. **Boundary:** P4-S31 through P4-S34 only. At this
package boundary P4-S35+ was not authorized; the later, separately authorized
P4-S35–S37 package is recorded in `P4_S35_S37_IMPLEMENTATION_CONTRACT.md`.

## Delivered safe presentation scope

| Session | Delivered runtime and UI |
| --- | --- |
| P4-S31 | Persian-first RTL Project Controls entry point with separately permissioned links to bounded comparison, exceptions and export. |
| P4-S32 | Read-only comparison of the project’s governing accepted-budget allocations against identically coded `approved` or legacy `recorded` expense allocations. Unallocated expense evidence is explicitly excluded and labelled. |
| P4-S33 | Scoped exception view for retained `advisory_only` overrun snapshots and, only when separately authorized, open immutable control-register observations. |
| P4-S34 | UTF-8 CSV of only those bounded comparison/exception rows. Every export records an append-only audit manifest with Tenant/project scope, digest, byte count and row-category counts. |

## Access, evidence and fail-closed boundary

`project_controls.compare`, `project_controls.exceptions_view` and
`project_controls.export` are distinct permissions, object-scoped through the
active membership and project. The export service rechecks the dedicated export,
comparison and exception permissions and never accepts a Tenant or project from
the request as authority. No source reference, source fingerprint, settlement,
AP, GL, Treasury, cash, contract, schedule calculation, forecast, risk score,
delay responsibility, contractual impact, candidate baseline, rebaseline, earned
value or Project Cost fact is exported or consumed.

P4-G01–G04 remain closed. P4-G06–G09 are read only through the existing accepted
governing budget and pinned expense allocation. P4-G10 remains `advisory_only`:
negative remaining values and retained overrun snapshots are evidence, not a
warning, hard stop, reservation, approval or budget mutation. P4-G11–G18 remain
closed; open register observations retain their existing unassessed fields and
are not scored or interpreted.

## Deferred remainder

P4-S38, all financial/source producer activation, warning policy, schedule integration,
baseline/change/rebaseline acceptance, forecast, risk, delay, contractual impact
and earned value remain blocked pending their separate Product Owner gates.
