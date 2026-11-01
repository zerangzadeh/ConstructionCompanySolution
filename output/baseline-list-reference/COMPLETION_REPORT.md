# Baseline List visual acceptance implementation — 2026-11-01

Authority: explicit bounded user request; UI and read-only journey adaptation only.
Reference: `C:/Users/azera/Downloads/BONIRA Persian Measurement & Progress UI Mockup.png` (visual reference, no implementation authority beyond the request).

## Repository grounding

Branch `main`; starting HEAD `5b760e85`; upstream comparison `0 0`.
The working tree already contained extensive uncommitted Contracts, Projects,
Payable List and shared component work. It was preserved. No branch/worktree,
staging, commit, push or merge was performed.

## Touch set

- `apps/billing/baseline_list.py`: validated list presentation over the existing authorized selector; global filters, choices, counts, sorting and pagination; scoped contract resolution; single approved record navigation.
- `apps/billing/views.py`: only baseline list/detail adapters changed by this request; pre-existing Payable List edits preserved.
- `apps/billing/templates/billing/baseline_list.html`: global/reference list, compact contract context, version table, real reasons, current badge and empty state.
- `apps/billing/static/billing/baseline_list.css`: opt-in baseline composition over existing Contracts list styles; responsive layout.
- `apps/billing/templates/billing/baseline_detail.html`: terminology and explicit return to all versions of the same contract.
- `apps/billing/templates/billing/journey_nav.html`: terminology only.
- `templates/contracts/detail.html`: baseline journey link label only; pre-existing edits preserved.
- `apps/billing/test_baseline_list.py` and `scripts/verification/baseline_list_validate.py`: isolated PostgreSQL tests and real installed Google Chrome via existing CDP driver.
- This evidence directory.

## Behavior and preservation

Global mode reuses Contracts list styles, shared filter bar, active chips, sorting
links and pagination. Filter choice querysets derive exclusively from the
existing authorized baseline queryset. Invalid filter choices return zero rows.
Scoped mode removes contract/project search and selectors and displays the
resolved contract number, title and project. The full version history remains
available. A redirect occurs only for one approved baseline and an unfiltered
contract entry; `versions=1` explicitly opens its list and prevents a redirect loop.
Multiple versions (including draft and superseded) always remain selectable.
The current badge derives strictly from existing `approved` state.
Only actual approval/withdrawal reasons are displayed. No pending review state,
Create route, Create button, or new workflow was invented.

Models, schema, migrations, service/domain rules, permissions, tenant/project
scope enforcement and Product Surface were not changed. Existing receivable-only
rules and one-current-approved constraint remain authoritative.

## Validation environment and coverage

Dedicated database: `test_bonira_baseline_list_ready_20261101`.
Cloned from existing clean synthetic test database
`test_bonira_payable_list_ready_20261101` (446 migrations; zero users) to avoid
rebuilding the large migration history. Development data was not changed.
An earlier fresh migration setup of `test_bonira_baseline_list_20261101` was
interrupted to use this faster equivalent isolated validation environment.

Command: `.venv/Scripts/python.exe scripts/verification/baseline_list_validate.py --reuse-db -q apps/billing/test_baseline_list.py --tb=short --junitxml=output/baseline-list-reference/tests.xml`
Result: **5 passed**. See `tests.log`, `tests.xml`.

Coverage: empty contract, one approved baseline redirect, explicit versions link,
multiple versions, current/superseded history, authentic reasons, global search,
filter chips, invalid choices, sorting, 26-record pagination, tenant separation,
project-restricted readers, inaccessible project/detail/filters, baseline-only
read permission and explicitly unprivileged reader.

Real Chrome scenarios (1440px desktop / 390px mobile): empty desktop/mobile,
Contract Detail → single baseline redirect, global desktop/mobile, multiple
versions desktop/mobile, superseded detail, project-restricted user and explicit
403 denial. See `browser/batch-*.json` and screenshots.

The first run revealed two test assumptions: the shell global search also has a
`q` input; the legacy member fixture has view permission. Assertions were scoped
to the page content and an explicitly unprivileged role was created. Product
permissions and the shared shell were not changed for these test assumptions.

Final browser-only rerun after simplifying the secondary action to match Contracts:
**1 passed** (`browser-tests.log`, `browser-tests.xml`), repeating all 10 scenarios
and additionally clicking the version sort and opening the row action menu.
The browser asserted that the menu is open, its detail action uses a valid URL in
a new tab, and it fits within the table boundary. Authorized browser pages returned
200, single-version navigation used 302 → 200, and the unprivileged user received
403. Final scenario records contain no JavaScript errors or unexpected HTTP errors.

Django system check: PASS. Ruff check and format: PASS. Scoped `git diff --check`:
PASS. Screenshot review: compact desktop table, contextual header, mobile cards,
no duplicate contract selection, and compact empty state without useless sorting
or pagination. Visual conformance means practical alignment with the reference
within the existing BONIRA shell, not pixel identity or Product Owner sign-off.

GLOBAL LIST UX: PASS
CONTRACT-SCOPED JOURNEY: PASS
VERSION HISTORY UX: PASS
BROWSER VALIDATION: PASS
REFERENCE VISUAL CONFORMANCE: PASS
PRODUCT OWNER VISUAL ACCEPTANCE: PENDING

Human Sign-off / Production Certification / Production Cutover: NOT EXECUTED.
No commit. No push.
