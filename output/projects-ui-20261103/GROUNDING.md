# Projects UI — execution context (2026-11-03)

Direct Human authorization: Projects List and Project Detail UI/UX from the two
visual references, real existing data only, browser verification, no commit/push.
This is bounded presentation work, not serial CEP execution. The explicit current
request supplies the separate Projects direction required by ui-guidelines §30.

Branch main; HEAD and origin/main 560bc3c9f136a3b76c6816dc127a80d74bcb7a1d;
ahead/behind 0/0. Initial unrelated changes: tailwind.css, reference_lists.py,
organizations/context_processors.py, base.html and untracked loading/profile/
operational-list work. Preserve these and concurrent unrelated work.

Touch set: Projects templates/workspace CSS/chart presentation, presentation-only
fields in the existing dashboard composition and list view, opt-in reuse of the
shared list CSS, existing header/icon/chart/sort components, scoped tests,
dedicated verification runner, validation report and this output directory.
No models, migrations, domain services, workflows, permissions, tenant policies,
production configuration, dependencies, Git writes or Registry changes.

Graph vocabulary queried read-only: project, dashboard, contracts, scope, cost.
Graph pointed to Projects service/domain source; current source inspected for
actual implementation. Existing get_organization_projects owns membership,
tenant/project scope, active-tenant and soft-deletion filtering. List status
aggregation runs on that service queryset, before UI filters/pagination.
ProjectCost projection and commercial summary retain existing source authority.
No financial total, cost recognition, progress or budget remainder introduced.

Existing Chart.js 4.6.1 local asset reused; no dependency/CDN introduced.
Existing provenance and MIT license remain unchanged.

Initial baseline test on the old generic test DB failed before reaching tests:
procurement_purchaseorder.source_award_id DuplicateColumn during test migrations.
Do not repair/change that database. A fresh dedicated PostgreSQL test DB is used:
test_bonira_projects_workspace_20261103. Only test migrations/fixtures run there.


Validation environment update: the original fresh-migration run was stopped in
its own test database to avoid unnecessary latency. A new dedicated DB,
`test_bonira_projects_workspace_ready_20261103`, was copied from the inactive
seeded `test_bonira_daily_list_ready_20261101` (446 recorded migrations, 669
business permissions, zero users). The source was read/copy-only and unchanged.
The single repository schema delta, procurement.0017_mvp04b_explicit_rfq_scope,
was applied by Django's test setup; the target has 447 repository migrations.
A migration-only JSON seed snapshot supports repeated isolated browser tests;
no development or production data is imported. The runner asserts the exact
test DB before flush/seed replay and restores the seed after each test session.

An early validation invocation overlapped clone creation and failed before tests
with a duplicate pg_database name. The dependent rerun followed clone completion.
First completed run: 23 PASS, 1 FAIL, 14 subtests PASS. The failed existing browser
scenario typed Gregorian text into enhanced Jalali fields. The test now supplies
formatted Jalali input through the existing UI conversion contract. Product date
parsing and domain semantics are unchanged.

Visual review found missing semantic color tokens in the opt-in reference list
foundation; the canonical success/warning/danger values are now defined there.
An empty inherited Contracts amount caption was removed from Projects by passing
no amount explicitly. Projects keeps its own 100%-width table to avoid clipped
row actions while preserving the shared list responsive pattern.
