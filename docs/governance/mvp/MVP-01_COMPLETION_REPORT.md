# MVP-01 — Product Surface Exposure & Navigation

**Status: COMPLETE — Development/non-production only.** Date: 2026-10-29 (Asia/Tehran).
AC-01–AC-14: **14/14 PASS**. This records package execution, not commercial MVP
readiness, Full ERP readiness, Human Sign-off or Production Certification.

## Authority, grounding and boundaries

The Human Product Owner's supplied MVP-01 instruction authorizes only bounded
local Development code/tests/documentation. Its SHA-256 is recorded in
[validation evidence](../../../output/mvp-01/VALIDATION.json). D1–D7 and the formal
CEP contracts/dependencies remain unchanged. The current MVP backlog/gap scope was
supplied in that instruction; no separate current local Gap Assessment/Advisor
Review Packet was located by the bounded filename search.

- Branch: `main`; starting/ending HEAD: `ccce8f43e15f1ca7e024a4fc3fa99335e4a1839b`.
- Starting `origin/main`: same SHA; local/upstream counts: `0/0`; starting tree: clean.
- Ending tree: only these MVP-01 changes, intentionally uncommitted.
- No branch/worktree creation, staging, commit, push, merge, rebase, tag, reset,
  stash or other Git write. The baseline comparison uses read-only `git show`.
- CEP Registry was inspected and left unchanged; this task is not a CEP lifecycle
  event. No completed CEP, canonical prompt, graph edge or historical evidence was amended.
- Migration: no business schema/data migration required, created or executed.
  Configured PostgreSQL **18.6**: `migrate --check --noinput` PASS;
  `makemigrations --check --dry-run`: **No changes detected**. Tests used the
  isolated Django PostgreSQL test database. No production action occurred.

## Actual implementation and touch set

The intended surface is the existing shared presentation/HTTP seam: exposure
policy, navigation/Home/search/shortcuts, route guarding, mixed reporting/workbench
presentation, and the minimum affected templates, tests and evidence. No models,
installed apps, URL namespaces, domain services, workflow runtime, producers,
resolvers or required backend handoffs were removed or disabled.

`core/product_surface.py` is the single exposure authority. Capability records
combine namespace defaults with explicit mixed-domain route overrides. One
permission-aware five-group destination catalogue feeds desktop/mobile and Home,
including existing guarded My Requests/manager availability for users without
back-office permission grants.
Existing business permission/scope resolution remains authoritative; exposure
only subtracts destinations. Unknown capability/namespaces fail closed.

`PRODUCT_SURFACE_PROFILE` defaults to `MVP`. `FULL_ERP` is an explicit server-owned
internal/test setting through this same policy. No customer switch, role bypass,
request/session/profile parameter or test-suite-wide bypass exists. Active tests
that inspect hidden internal surfaces opt in individually.

The HTTP middleware applies a negative exposure boundary after authentication and
organization middleware, before hidden handlers can read/mutate business data.
It redirects unauthenticated hidden requests to login and returns a controlled
Persian 403 for authenticated hidden requests, including POST/HTMX. Passing this
boundary grants nothing: original permission/object/project/site and service
checks still run. Existing namespaces and non-HTTP backend calls remain intact.

Shared breadcrumbs, empty-state actions, record-detail links, financial shortcuts,
relevant cross-module links and dynamic workbench source links use the same
policy. Search remains bounded to Projects and Materials. Home only regrouped
existing entry destinations; no new dashboard/KPI/chart or visual theme was added.

Reporting retains the operational procurement-cycle and inventory quantity/value
families after existing source authorization; internal financial projections,
reconciliation, source manifests, and technical export/refresh surfaces stay hidden.
Backend reporting services and source authority are unchanged.

Customer workbench counts/filters/rows omit hidden subjects. Claim/release/action
HTTP handlers reject hidden subjects before invoking the unchanged workflow
runtime. Existing source ownership, candidacy, scope and transactional authorization
remain in the runtime; exposure adds no permission requirement to visible actions.

## Mixed-domain preservation

- **Expenses/Petty Cash:** Expense list/draft/detail/recurrence access remains
  available under existing permissions. Current expense lifecycle, reimbursement
  source requests and Treasury advance/settlement/reversal/reconciliation tests
  pass. Treasury remains cash authority; its workspace stays hidden. No parallel
  cash logic or new Petty Cash UI was introduced.
- **Workforce/Timekeeping:** existing employee operational entries, crews and
  project/site assignments remain visible. Full HR, employment administration and
  Full ESS entry surfaces remain hidden. The existing My Requests own-Timekeeping
  status route is visible only for `leave`, `overtime`, and `correction` sources;
  its explicit Person/WorkRelationship and own-source checks remain in force.
  HR/payroll source kinds, missing identity and unavailable sources fail closed.
  No Worker model, national-ID change or simplified Field Workers redesign was made.

## Validation and regression attribution

| Execution | Result |
| --- | --- |
| Final focused policy/Home/navigation/search + actual Chrome | **38 PASS**, 0 FAIL; 16 subtests PASS |
| Affected regression (including legacy Home browser states) | **88 PASS**, 1 proven pre-existing FAIL; 57 subtests PASS; 2 known baseline query cases deselected |
| Distinct passing test methods across those executions | **91** (overlap counted once) |
| Real Chrome scenarios A–G and mixed/operational checks | **17/17 navigations PASS** |
| Django system check | PASS |
| Ruff check / format check | PASS — 21 changed Python files |
| Changed template compilation | **19/19 PASS** |
| Shared static-file discovery | **6/6 PASS** |
| Browser probe JavaScript syntax / `git diff --check` | PASS |

Browser verification uses isolated synthetic tenant accounts and a real Django
live server. It verifies authorized ordinary and customer-admin navigation,
insufficient permission, hidden and visible direct URLs, Expenses draft access,
Workforce/Timekeeping, own-source status, operational Reports, Safety and Quality.
Desktop and mobile groups agree. Home has no horizontal overflow; mobile drawer
opens. All rendered local links in those scenarios are checked against the central
policy. Desktop/mobile screenshots were visually inspected.

[Desktop Home](../../../output/mvp-01/browser/mvp01-browser-admin-A-C-home-desktop.png)
· [Mobile navigation](../../../output/mvp-01/browser/mvp01-browser-admin-A-C-home-mobile.png)
· [Ordinary restricted user](../../../output/mvp-01/browser/mvp01-browser-reader-B-ordinary-home.png)
· [Raw browser results](../../../output/mvp-01/browser/mvp01-browser-admin-results.json).
Historical browser outputs were preserved; the older Home browser test now writes
its disposable captures into a temporary directory.

No attributable regression remains. Surface-stale expectations were updated
narrowly (old NAV placeholders, Support alerts, hidden internal detail routes).
An unregistered dummy URL in the escaping test was replaced with a registered
Documents URL; escaping and fail-closed destination checks remain intact.

The following are **PRE_EXISTING / OUT_OF_SCOPE**, not accepted as new package risk:

1. Two workbench query-ceiling tests record **81 queries versus limit 45** both
   before and after MVP-01. No threshold was loosened.
2. All 15 legacy `apps/expenses/tests.py::ExpenseServiceTests` fail in their shared
   setup: the old unbootstrapped membership cannot call `create_project`, before
   any changed HTTP/presentation code. A representative test reproduces identically
   against HEAD. Current governed `ExpenseControlTests` pass, including lifecycle,
   reimbursement, financial boundaries, UI and tenant/permission cases.
3. The legacy Timekeeping browser-response assertion expects the removed Persian
   phrase “پیش‌نمایش فقط دقیقه‌ها”. It fails identically with HEAD code/templates.
   The actual workbench returns 200 in both builds; current MVP browser checks and
   Timekeeping scope regression pass. Its unrelated wording was not rewritten.

Reproducer: `scripts/verification/mvp01_head_baseline.py` loads the original eight
affected Python modules and original changed templates from HEAD into an isolated
pytest process, omits the new middleware, and leaves all working-tree files and
Git state untouched. See the commands and local logs below. The full unrelated
suite was not run; this is bounded affected regression evidence.

## Acceptance evidence

| Criterion | Result and evidence |
| --- | --- |
| AC-01 | PASS — one policy consumed by HTTP, shared navigation/Home, search and template adapters |
| AC-02 | PASS — Workforce, Organizations, Expenses and Reporting route-level mixed cases; source-kind-aware own status |
| AC-03 | PASS — five approved Persian navigation families, real desktop/mobile rendering |
| AC-04 | PASS — effective permissions/scopes intersect with exposure; empty groups omitted |
| AC-05 | PASS — hidden links absent from tested shared/customer entry points and dynamic source links |
| AC-06 | PASS — authenticated hidden GET/POST/HTMX denial; namespaces retained |
| AC-07 | PASS — visible operation routes, current Expense lifecycle and approved workbench actions remain functional |
| AC-08 | PASS — Treasury source handoffs and Workforce/Timekeeping/own-status preservation |
| AC-09 | PASS — insufficient permission, missing identity, revoked membership, forged tenant and foreign object denial |
| AC-10 | PASS — no app/model/FK/migration/service/runtime/resolver removal; backend preservation tests |
| AC-11 | PASS — no business migration; configured migration check and drift check pass |
| AC-12 | PASS — Home information architecture grouping only; current styling reused |
| AC-13 | PASS — focused policy/navigation/Home/HTTP/mixed-domain automated checks |
| AC-14 | PASS — 17 real Chrome navigations, screenshots and existing responsive Home state regression |

## Commands and local logs

All Python commands use `.venv/Scripts/python.exe`. The JSON evidence records
counts, baseline attribution, branch/HEAD, authorization hash and complete file list.

Final focused/browser:

```powershell
.venv/Scripts/python.exe -m pytest core/test_product_surface.py core/test_home.py core/test_cep017_navigation.py core/test_cep019_search.py core/test_product_surface_browser.py -q --reuse-db --disable-warnings --tb=line
```

Affected regression targets: `core/test_product_surface.py`, `core/test_home.py`,
`core/test_cep017_navigation.py`, `core/test_cep019_search.py`,
`core/test_cep014_administration.py`, `core/test_list_detail_navigation.py`,
`core/test_list_detail_resolution.py`, `apps/workflows/test_workbench.py`,
`apps/expenses/test_p4_s26_s30.py`, the two TreasuryFoundationTests for reimbursement
and advance settlement, the Timekeeping workbench/scope cases, and
`core/test_home_browser.py`. The two baseline query-bound methods were excluded
from this final execution after unchanged-HEAD reproduction.

```powershell
.venv/Scripts/python.exe scripts/verification/mvp01_head_baseline.py apps/workflows/test_workbench.py::WorkbenchTests::test_pagination_responsive_context_and_query_bound apps/workflows/test_workbench.py::WorkbenchTests::test_high_open_item_volume_keeps_page_and_query_count_bounded apps/expenses/tests.py::ExpenseServiceTests::test_create_expense_records_decimal_amount_and_audit -q --reuse-db --disable-warnings --tb=line
.venv/Scripts/python.exe scripts/verification/mvp01_head_baseline.py apps/timekeeping/test_p7_s06_s12_timekeeping.py::P7TimekeepingTests::test_persian_workbench_is_reachable_from_navigation -q --reuse-db --disable-warnings --tb=line
```

Local detailed logs (ignored log artifacts, intentionally retained in this workspace):
`output/mvp01-final-focused-browser.log`, `output/mvp01-final-regression.log`,
`output/mvp01-boundary-regression.log`, `output/mvp01-head-baseline.log`, and
`output/mvp01-timekeeping-baseline.log`.

## Documentation and handoff

ROADMAP now records the approved eight-package MVP delivery sequence without
creating another registry or changing CEP edges. Product Strategy changed only
its section-8 implementation-status wording. D1–D7, Agents, UI guidelines and stack
contracts remain unchanged; existing presentation components/colors were reused.

MVP-02 through MVP-08 remain unstarted: Field Workforce, Billing journey,
Procurement/Inventory journey, XLSX/P0 outputs, critical print, P1/usability, and
demo/release verification/Human UAT. No automatic continuation is authorized.

Git writes: **NONE**. Human Sign-off, Production Certification and production
deployment/migration/cutover: **NOT EXECUTED**.

## Complete changed-file inventory

- `ROADMAP.md`
- `apps/organizations/context_processors.py`
- `apps/reporting/templates/reporting/_read_model_card.html`
- `apps/reporting/views.py`
- `apps/workflows/views.py`
- `apps/workflows/workbench.py`
- `config/settings/base.py`
- `core/financial_navigation.py`
- `core/home.py`
- `core/product_surface.py`
- `core/product_surface_middleware.py`
- `core/search.py`
- `core/templatetags/product_surface.py`
- `core/test_cep014_administration.py`
- `core/test_cep017_navigation.py`
- `core/test_home.py`
- `core/test_home_browser.py`
- `core/test_list_detail_navigation.py`
- `core/test_list_detail_resolution.py`
- `core/test_product_surface.py`
- `core/test_product_surface_browser.py`
- `core/views.py`
- `docs/architecture/PRODUCT_VISION_AND_MVP_RELEASE_STRATEGY.md`
- `docs/governance/mvp/MVP-01_COMPLETION_REPORT.md`
- `output/mvp-01/VALIDATION.json`
- `output/mvp-01/browser/mvp01-browser-admin-A-C-home-desktop.png`
- `output/mvp-01/browser/mvp01-browser-admin-A-C-home-mobile.png`
- `output/mvp-01/browser/mvp01-browser-admin-F-expenses.png`
- `output/mvp-01/browser/mvp01-browser-admin-G-workforce.png`
- `output/mvp-01/browser/mvp01-browser-admin-results.json`
- `output/mvp-01/browser/mvp01-browser-reader-B-ordinary-home.png`
- `output/mvp-01/browser/mvp01-browser-reader-results.json`
- `scripts/verification/mvp01_browser.mjs`
- `scripts/verification/mvp01_head_baseline.py`
- `templates/base.html`
- `templates/components/empty_state.html`
- `templates/components/navigation_links.html`
- `templates/components/page_header.html`
- `templates/components/record_detail_link.html`
- `templates/equipment/detail.html`
- `templates/home.html`
- `templates/organizations/select.html`
- `templates/organizations/settings.html`
- `templates/projects/controls.html`
- `templates/reporting/dashboard.html`
- `templates/workflows/_work_item_row.html`
- `templates/workflows/manager_workspace.html`
- `templates/workflows/my_requests.html`
- `templates/workforce/_ess_navigation.html`
- `templates/workforce/_tabs.html`
- `templates/workforce/employee_detail.html`
- `templates/workforce/personal_change_status.html`
