# Platform Admin dashboard redesign

Implemented on 2026-11-07 in `E:/Construction_Company_Solution`. Branch `main`, HEAD and local upstream reference `1d3593a91536477fcfd146a522701980b9ebf205`. The existing dirty working tree, including the earlier Platform Admin completion, was the starting point. Unrelated changes were preserved.

## Result and reference comparison

The dashboard follows the supplied image's RTL hierarchy, navy sidebar, compact header, five tinted KPI cards, three main panels and lower quick-action/health panels. BONIRA's existing logo, Persian typography and canonical colors are used. The header identifies the platform workspace and shows the existing account controls. Platform pages display the operational platform role independently of the user's active tenant role.

| Reference area | Implemented behavior |
| --- | --- |
| Sidebar | Seven existing destinations with consistent icons, active-page indication, actual product profile and POST logout. Desktop and mobile use the same navigation include. |
| KPI cards | Database-backed company total, active and suspended companies, registered accounts and memberships. Accounts and memberships retain separate labels and sources. |
| Company status | Compact doughnut and exact accessible counts for active, suspended, cancelled and archived companies. Deleted companies are excluded. |
| Platform activity | Actual permitted administrative audit counts for seven calendar days in the request timezone. A bar chart and exact daily values use the existing chart facilities. |
| Recent events | Four recent administrative events with action, actor, permitted company/global context and timestamp, plus the existing audit link. Raw metadata is excluded. |
| Quick actions | Existing company creation, business-role catalog, platform administrators and platform settings URLs. Operator management is omitted when its registered capability is disabled. |
| Health | Existing database/cache probes, explicit unreachable/unverified states and the existing status link. The check time is displayed. |

The read-only activity series replaces the reference's unsupported membership-growth curve. Historical growth percentages, search, notifications and an application-health tile were omitted because the current dashboard supplies no corresponding verified data or functional controls. Existing onboarding warnings remain as a compact conditional notice.

## Changed files and reuse

- `templates/organizations/platform_dashboard.html` implements the dashboard composition using existing `components/dashboard_metric.html`, `components/dashboard_chart.html` and the icon component.
- `templates/organizations/{platform_navigation,platform_health_signals}.html` adds navigation icons and an optional compact health presentation. The status page retains its existing full health presentation.
- `templates/base.html` loads the platform stylesheet conditionally and adapts platform branding, header and profile indication. `templates/components/header_profile.html` distinguishes the platform role. `templates/components/form_icon.html` extends the existing inline SVG icon catalog.
- `apps/accounts/static/css/erp_platform.css` supplies scoped platform styling and responsive rules. `apps/accounts/static/css/tailwind.css` was rebuilt through the existing asset command.
- `apps/organizations/platform_console.py` adds read-only dashboard presentation aggregates and chart data. Existing mutations, role services, URLs, tenant access checks and Product Surface policy retain their authority. `apps/organizations/context_processors.py` supplies icon names and the actual product profile.
- `apps/projects/static/projects/dashboard_charts.js` accepts the platform JSON source in addition to the existing project source and recognizes suspended/archived colors. The locally vendored Chart.js library and existing accessible chart component are reused.
- `apps/organizations/test_platform_console.py` checks the new data projections, action availability, empty state and the revised navigation composition.

This redesign introduces zero migrations and zero dependencies. No production operation, commit or push was performed.

## Verification

Database tests reused the isolated PostgreSQL database `test_bonira_platform_completion_01a1b05d`, created during the preceding task. Environment databases were not migrated for this redesign.

- 79 distinct focused tests PASS across the completed selections, covering the console, platform companies, P1.1 authorization, CEP-014 administration, Product Surface and project command-center regression tests. The final console/project selection reports 22 PASS and 12 passing subtests. The other 57 permission/exposure tests passed in the preceding selection.
- The initial new lifecycle-count fixture violated the existing archive-state database constraint. Its status and timestamp were corrected together. The final console selection passes, including lifecycle totals, exclusion of deleted companies, audit date bounds, safe projection, quick-action URLs, disabled capabilities and zero-company behavior.
- Django system check PASS. Organizations migration-drift check PASS. Focused Ruff lint/format checks PASS. JavaScript syntax and whitespace checks PASS.
- CSS build PASS, with an existing non-blocking outdated Browserslist metadata notice.
- Node checks PASS for platform and legacy project chart mounting, exact values, suspended-state color, RTL tooltip configuration and missing-library/drawing-failure fallbacks. PostCSS syntax parsing PASS. These are code checks, independent of browser rendering.

## Responsive and browser evidence

| Width | Implemented CSS layout | Actual browser result |
| --- | --- | --- |
| 1440 px | Right sidebar, five KPIs, three main panels and two lower panels. | Unverified. |
| 1024 px | Right sidebar, three-column KPI grid, recent events across the row and two chart columns. | Unverified. |
| 768 px | Drawer navigation, three-column KPIs, recent events across the row and two chart columns. | Unverified. |
| 390 px | Drawer navigation, two-column KPIs, single-column panels and compact header controls. | Unverified. |

The browser tool's current `local-web-development` capability reports that local browser use is disabled in Work settings. No browser screenshot or pixel-level visual comparison was produced. Absence of horizontal overflow, rendered contrast, chart resizing, keyboard behavior and visual closeness at the four requested widths require an enabled local-browser session. Code and template comparison against the reference confirms the intended structure and styling only.

Exact server-rendered chart values remain available when JavaScript or Chart.js fails. Health reflects dependency reachability. Production readiness requires its separate operational evidence.
