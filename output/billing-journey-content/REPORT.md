# Billing journey content and recent-page visual consistency

Date: 2026-11-01. Explicit user authorization: inspect supplied Claims/Baseline/
Progress screenshots and correct defects; keep visual treatment consistent with
recent BONIRA pages. Branch main; HEAD 5b760e85. Existing dirty/untracked work
preserved; no stage, commit, push, merge, branch or worktree creation.

## Findings

The screenshot named billingbaselines shows a **Baseline Detail**, identified by
its version/status and priced baseline rows, not a Claim Detail. Progress List
correctly shows measured period/cumulative quantities, not claim monetary totals.
Clicking the already-active Claims tab reloads that collection route as expected.
Existing named journey routes, context and permission checks remain unchanged.

The huge gap between baseline header/body in the supplied screenshot was not
reproduced in Chrome, including before edits at 1440×900, 1920×2117 and 390×900.
We do not claim a proven root cause or permanent fix for that captured artifact.
Final desktop geometry asserts that the first row follows the header within 8px;
mobile uses the same responsive card pattern as recent reference lists.

## Changes

- Baseline Detail: explicit entity/version title; contract/project as secondary
  context; all-versions and existing create-claim route as secondary actions;
  effective date, real ceiling/currency, existing status; separate unit, quantity,
  unit-rate and value columns. No invented current-version badge or lifecycle
  command. Existing create_url and Product Surface check retained.
- Baseline List: description corrected from approved versions to versions,
  since this list includes drafts/history too.
- Progress List: title aligned with کارکرد و پیشرفت; description, contract/project
  hierarchy, independent unit column. Official Contracts list header, working
  context, search/filter chips, result summary, responsive table/cards and
  pagination reused. Existing GET search/contract context, results, ordering and
  pagination semantics retained. No unsupported filters or sorting added.
- Page-scoped journey_content.css adapts official erp_reference_list.css; final
  review corrected inherited hiding of Search submit in a no-quick-filter list.
- list_presentation.py creates presentation-only form/chip state using the
  already-authorized, filtered and paginated results. views.py changes are only
  the corresponding context helper invocation (views-style.diff).

Product touch set: three Billing templates, billing/views.py presentation context,
new billing/list_presentation.py and billing/static/billing/journey_content.css.
New test: billing/test_journey_content.py. Evidence stays in this directory.
No Domain/Model/Migration, financial calculations, workflows, permissions,
selector authority, tenant/project scope, Product Surface or dependencies changed.
No Development data mutation.

## Validation

- before-validation.txt: 1 browser geometry test PASS over 3 viewports before
  changes; isolated synthetic PostgreSQL, installed Chrome via existing CDP driver.
- style-validation.txt: 7 server tests PASS (new search/context/chips/clear,
  existing navigation permissions and baseline routing/isolation); browser
  assertion initially expected hidden desktop headers in mobile innerText.
  Corrected test to respect responsive cards and revalidated.
- final-browser-validation.txt: 1 browser test PASS, 6 scenarios: Baseline Detail
  1440×900, 1920×2117, mobile; Progress desktop/mobile including visible Search
  submit; actual mouse click Claims → Baseline Detail with contract context.
- browser/batch-baseline-1440-900.json and screenshots: measured layout and
  actual route results. Final images visually reviewed for desktop/mobile.
- Ruff check/format, Django system check, changed-file git diff --check: PASS.

The former interactive desktop browser session could not be inspected because
Computer Use stopped on URL-confidence enforcement. All subsequent browser
claims refer to installed real Chrome in the isolated headless test environment,
not the user's authenticated 127.0.0.1:8000 session.

Product Owner visual acceptance: PENDING.
Git commit/push: NOT EXECUTED.

Final visual polish reuses the official list-filter-bar ID and flex layout so
Search sits beside the input on desktop and the magnifier has sufficient text
padding. search-browser-validation.txt records the final desktop/mobile mouse
submissions, retained contract query and active filter chips. The scenario
screenshots are progress-search-False/True in browser/. All layout checks refer
to the actual viewport; mobile CSS pseudo-element labels are verified through
responsive rendering rather than hidden desktop header innerText.

Final verification outcomes:
- 7 server tests PASS (style-validation.txt; its original browser-only failure
  was an assertion about mobile hidden headers, subsequently corrected).
- 6 geometry/content/navigation scenarios PASS (final-browser-validation.txt).
- 2 final Search submission scenarios PASS (search-browser-validation.txt),
  including the final ID/flex/padding fixes. Desktop/mobile images reviewed.
- 8 final Chrome scenarios total; no document horizontal overflow.
- BASELINE CONTENT UX: PASS; PROGRESS LIST UX: PASS;
  RECENT-PAGE VISUAL CONSISTENCY: PASS; BROWSER VALIDATION: PASS.
- ORIGINAL SCREENSHOT GAP ROOT CAUSE: NOT REPRODUCED.
- PRODUCT OWNER VISUAL ACCEPTANCE: PENDING.
