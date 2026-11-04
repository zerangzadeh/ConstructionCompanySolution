# Home / My Workspace redesign

Date: 2026-11-04. Direct Human request authorizes this bounded, non-production
presentation change. Product Owner acceptance remains PENDING.

## Result and boundaries

Home now presents a personal greeting and active organization, source-backed KPI
cards, assigned workflow work, recent visible records, six bounded quick links,
the project-status doughnut and compact operational summaries. Desktop follows
the supplied reference's hierarchy, three-column workspace, semantic colors and
card treatment. Mobile prioritizes assigned work and stacks the panels in RTL.
The photographic reference banner is interpreted as a local construction outline;
sample identities, counts, warning labels and financial amounts are not copied.

The existing Header, Sidebar, Context Selector, personal settings and shared
icons/chart components remain in use. The existing shared identity partial had
an absent-position placeholder; its single position line now renders only when
an actual position title exists. Existing role and identity resolution is unchanged.

No model, migration, domain service/calculation, workflow semantics, permission,
scope enforcement, Product Surface architecture or CEP/Registry state changes.
No new dependency: reuse the existing local Chart.js 4.6.1 with its existing
license/provenance. JavaScript only renders the server-produced chart.

## Data provenance

| Display | Authoritative source |
| --- | --- |
| Active projects, total and status distribution | `get_organization_projects`; model `ProjectStatus`; count of scoped records |
| Active contracts and total contracts | `get_organization_contracts`; `ContractStatus.ACTIVE` |
| Daily reports | `get_organization_daily_reports`; all visible records, not a fabricated today count |
| Submitted purchase requests | `get_organization_purchase_requests`; `PurchaseRequestStatus.SUBMITTED` |
| Estimate total | `get_organization_estimates` |
| Assigned-work count/list/priority | `build_workbench` and `decorate_work_items`; same exposed adapters as the existing Workbench |
| Recent activity | Up to six most recently updated authorized source records, explicitly described as record updates; actual `updated_at`, existing detail URL |
| Quick access | Existing `authorized_home_links`, capped at six; source-denied families are removed |

All source calls use the authenticated user and server-resolved organization.
Existing selectors own membership, tenant state, project/site scope and soft-delete
rules. Product Surface governs routes and workflow subject families. UI visibility
never grants authority. Counts cover **all permitted projects in the active
organization**, as stated on screen; the selected project context does not silently
change their meaning. Recent timestamps render in the organization's timezone.

Recent activity is a bounded record-update view across projects, contracts, daily
reports, estimates and purchase requests, not a complete audit/event feed. No
financial totals, worker counts, overdue reports, fabricated trends or project
warnings are added. Workflow priority labels reuse the existing rules. Empty and
unauthorized families remain hidden or have truthful empty states; a zero-project
organization has no invented doughnut. Accessible source values remain when
JavaScript or the chart library is unavailable.

## Validation

Dedicated PostgreSQL database: `test_bonira_home_ready_20261104`, cloned from the
existing migrated test fixture after verifying 447 migrations and zero users,
organizations and projects. The source fixture is unchanged. No development
business records were created or edited. A slow initial empty migration bootstrap
was abandoned and removed. All synthetic business fixtures live in the isolated
test database, which the runner restores to its migration seed.

Final bounded run: **37 tests and 6 subtests PASS**, including Home states,
source-based values, all Home destination HTTP checks, project scope, active
organization switch, hidden Product Surface facts, shared-header identity and
the personal-requests-only Home regression.

**13 real installed headless Chrome scenarios PASS**: 1672/1440/1024/390 widths,
a full desktop view, limited-project user at desktop/mobile, empty organization
at desktop/mobile, another active organization, blocked chart asset, disabled
JavaScript and exact Persian RTL tooltip formatting. Zero viewport overflows,
JavaScript exceptions, page/asset HTTP errors and external frontend requests.
The existing shell favicon 404 is excluded by the repository's browser driver.
Desktop, mobile, empty and restricted screenshots were visually reviewed.
After the final banner illustration sizing adjustment, the desktop/mobile browser
test was rerun: **1 test / 5 Chrome scenarios PASS** (`visual-final.xml`).

The first run retained at `tests.xml` had 19 passes, a raw-string test false
positive (`/static/projects/...` mistaken for a project link), the existing shared
position-placeholder finding, and test teardown errors from retained Payment FKs.
The link assertion now checks an actual `href`; the placeholder is removed; the
browser fixture reuses the repository's existing isolated cascading teardown.
These are superseded by the passing `verified.xml` run. Earlier results remain
available rather than being rewritten.

Commands:

```powershell
.venv/Scripts/python.exe scripts/verification/home_workspace_validate.py core/test_home.py core/test_home_workspace.py core/test_home_workspace_browser.py tests/test_header_identity.py core/test_product_surface.py::ProductSurfaceHttpTests::test_home_keeps_own_requests_without_backoffice_permissions --reuse-db -q --tb=short --junitxml=output/home-workspace-20261104/verified.xml
.venv/Scripts/python.exe scripts/verification/home_workspace_validate.py core/test_home_workspace_browser.py::HomeWorkspaceBrowserTests::test_desktop_tablet_mobile_donut_and_links --reuse-db -q --tb=short --junitxml=output/home-workspace-20261104/visual-final.xml
.venv/Scripts/python.exe manage.py check
.venv/Scripts/python.exe -m ruff check core/home_workspace.py core/views.py core/test_home.py core/test_home_workspace.py core/test_home_workspace_browser.py scripts/verification/home_workspace_validate.py
.venv/Scripts/python.exe -m ruff format --check core/home_workspace.py core/views.py core/test_home.py core/test_home_workspace.py core/test_home_workspace_browser.py scripts/verification/home_workspace_validate.py
git diff --check -- core/views.py core/test_home.py templates/home.html
```

Evidence: [JUnit](../../output/home-workspace-20261104/verified.xml),
[browser results](../../output/home-workspace-20261104/browser/HomeWorkspaceBrowserTests/),
[desktop](../../output/home-workspace-20261104/browser/HomeWorkspaceBrowserTests/procurement-owner-home-full-desktop.png),
[mobile](../../output/home-workspace-20261104/browser/HomeWorkspaceBrowserTests/procurement-owner-home-390.png).

## Repository closeout

Branch `main`; start/end HEAD and `origin/main`:
`560bc3c9f136a3b76c6816dc127a80d74bcb7a1d`. Existing dirty changes were preserved.
The only overlap with pre-existing untracked implementation is the conditional
position line in `templates/components/user_identity_labels.html`.

Touch set: `core/views.py`, new `core/home_workspace.py`, `templates/home.html`,
new `templates/components/home_metric.html`, that shared position line, new
`apps/accounts/static/css/erp_home.css`, `core/test_home.py`, two new Home test
modules, new `scripts/verification/home_workspace_validate.py`, this report and
isolated test evidence. The header regression also regenerates its existing
synthetic evidence under `output/header-identity/`.

No branch/worktree, staging, commit, push, merge, deployment or production action.
Human Sign-off / Production Certification: NOT EXECUTED.

```text
HOME PAGE UX: PASS
REAL DATA COMPLIANCE: PASS
PERMISSION & TENANT ISOLATION: PASS
BROWSER VALIDATION: PASS
VISUAL REFERENCE CONFORMANCE: PASS
PRODUCT OWNER ACCEPTANCE: PENDING
```
