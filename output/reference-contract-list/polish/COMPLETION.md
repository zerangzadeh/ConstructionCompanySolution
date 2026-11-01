# Contracts List — final visual polish

2026-11-01 (Asia/Tehran). Branch `main`, unchanged HEAD
`5b760e853b329e2b03415da7b046641359db6a62`; `origin/main` matches.
The pre-existing uncommitted Reference List implementation was preserved and
refined under the explicit pasted request. No broad audit, redesign, module
rollout, shell change, MVP-04 work, commit or push.

## Files changed in this pass

- `templates/contracts/list.html`: grouped header, result toolbar, amount label,
  visible existing detail action and stylesheet cache version.
- `templates/components/filter_bar.html`: aligned search label, active-chip strip
  only when applicable, count moved into result toolbar, script cache version.
- `templates/components/list_result_toolbar.html`: shared count/current-sort strip.
- `apps/accounts/static/css/erp_reference_list.css`: spacing, control heights,
  column balance, title hierarchy, subtle link/hover treatment, tabular amounts,
  compact advanced panel and existing responsive cards.
- `apps/accounts/static/js/erp_filter_bar.js`: moves the same reset link beside
  Apply on desktop and into the visible chip group on mobile; no URL/filter logic.
- `apps/contracts/views.py`: presentation labels for the existing allowlisted sort
  only; filtering, ordering, scope checks, queries and calculations are unchanged.
- `apps/contracts/test_reference_list_browser.py`: verifies displayed sort label,
  title-to-Detail navigation and return with filters retained.
- `templates/components/README.md`: documents the toolbar and responsive reset.
- This evidence directory: four AFTER screenshots, scenario outputs and test log.

Previously modified `templates/base.html` and other Reference List foundation
files were not changed by this polish pass. No models, migrations, domain rules,
calculations, workflows, permissions, tenant/project scope, Product Surface policy,
direction semantics or dependencies changed. No production action or Human visual
acceptance is claimed.

## Visual result

Breadcrumb, title, description and CTA now read as one compact unit through the
existing header's `page_actions_near_title` option. The workspace follows directly,
with aligned 38px quick controls and a distinct count/sort toolbar adjoining the
table. Apply and clear-all are grouped on desktop, while reset stays accessible
when mobile filters are collapsed. Advanced filters default closed and occupy
approximately 91px when opened at 1440px; active advanced queries retain the
existing restored-open behavior.

Rows give contract titles the strongest emphasis, retain project metadata below,
keep canonical contract numbers Latin/LTR, align amounts with Persian tabular
figures, and show explicit detail links. Row hover strengthens the title link.
Existing restrained status badges, direction wording and mobile cards remain.

The result toolbar shows the actual filtered count and current supported ordering.
No total, export, extra sort, bulk action or menu was introduced. There is no
existing aggregate/export presentation contract, and this pass preserves existing
financial calculations. The reference's sidebar geometry/menu density still
differs from the retained application shell, which this request excludes.
This is an agent visual-conformance assessment, not Product Owner acceptance or
pixel identity with the generated preview.

## Validation and evidence

`run_validation.py` reuses the established isolated PostgreSQL test database
`test_bonira_mvp03_20261029`, redirecting evidence to this directory so prior
historical artifacts remain untouched.

```text
.venv/Scripts/python.exe output/reference-contract-list/polish/run_validation.py
10 passed, 8 subtests passed in 103.61s
Exit code: 0
```

See [tests.log](tests.log) and [VALIDATION.json](VALIDATION.json). The two browser
test methods cover 20 real Chrome scenarios at 1440px desktop / 390px mobile:
general and project-scoped lists; per-source and combined search; status; both
contract sides; project selection including remote options; advanced open/close,
apply and state restoration; active chips; remove one; clear-all; pagination with
filters/context retained; existing sorting; Contract Detail navigation and return;
RTL/LTR; mobile card layout; no technical leakage or horizontal page overflow.
Validated documents return HTTP 200, except the deliberate permission-denied
scenario (HTTP 403). No validated list or Detail navigation returned 404/500.

Final checks: Django system check, Ruff check/format, JavaScript syntax and
`git diff --check`: PASS. No broader ERP regression is claimed.

Interactive Chrome review additionally confirmed equal 38px control heights,
single-row desktop filter/actions, the compact advanced-panel height, and a 390px
viewport with document `scrollWidth == clientWidth == 375` and grid/card rows.
Temporary viewport emulation was reset after inspection.

AFTER captures (1440×1000 desktop; 390×844 mobile), directly reviewed against the
approved reference direction and the prior implementation:

- [Desktop default](desktop-default.jpg)
- [Desktop filtered](desktop-filtered.jpg)
- [Desktop Advanced Filters open](desktop-advanced.jpg)
- [Mobile default](mobile-default.jpg)

CONTRACT LIST FUNCTIONAL VALIDATION: PASS  
CONTRACT LIST BROWSER VALIDATION: PASS  
REFERENCE VISUAL CONFORMANCE: PASS  
PRODUCT OWNER VISUAL ACCEPTANCE: PENDING
