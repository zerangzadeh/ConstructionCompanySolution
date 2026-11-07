# Dashboard and Reporting UI standardization

Direct Human request, 2026-11-05; continued 2026-11-06 (Asia/Tehran).
Prerequisite: Operational Workspace technical rollout complete per
`output/operational-workspace/REPORT.md`; Product Owner acceptance pending and
two original-template query-budget failures retained.

Branch main; HEAD and origin/main 59f2fde64fc3684f09871b82a2b1945905c28aab.
Existing dirty tree preserved using baseline copies of overlapping templates and
guidelines and narrow patches to the recorded touch set. No Git writes.

Pilot: projects:detail (real budgets, scoped expense evidence, site/contract counts;
no supported physical-progress series). Dashboard adopters: Home, Project detail,
reporting:dashboard, billing:commercial_control_dashboard. Reporting adopters:
Project control comparison/exceptions, Inventory valuation, Billing statutory
operations (specialized multi-source layout retained).

Preserved: accepted Project List summary/list, record lists including Daily Reports
and XLSX outputs, accepted contract/detail dashboards, Equipment cost workbench
(policy/allocation mutations), completed operational workspaces. Hidden
Accounting/Treasury/HR/Payroll/financials and reporting drill-through/export/
reconciliation remain excluded. No route, model, migration, service, permission,
calculation, filter or export semantics change.

One presentation query optimization: Inventory valuation eagerly loads the already
related pool/movement units for explicit quantity labels. Selection, tenant scope,
limits, services and data behavior remain identical; no per-row unit queries.

Touch set: the eleven baseline UI/doc files, opt-in dashboard/report CSS, shared
assets and metric includes, focused tests/browser fixtures and isolated verification
runner, evidence here. Existing shared Filter Bar/Header/Badge/chart/List components
and global CSS are read-only.
