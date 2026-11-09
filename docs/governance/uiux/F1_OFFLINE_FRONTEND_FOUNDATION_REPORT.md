# F1 — BONIRA Offline Frontend Foundation

**Current scoped F1 result after remediation (2026-11-02): PASS.** The complete
focused command still reports **FAIL** for 23 reproduced baseline failure events;
none is an outstanding F1 regression. The F1 prerequisite for F2 is **OPEN**.
The current assessment and acceptance evidence are in the remediation section
below. Earlier failed commands and their original evidence remain failures.

## Entry assessment (recorded before implementation, 2026-11-02)

- Authority: the user's bounded F1 request. Stop after F1; no F2, F3 or MVP-05;
  no commit or push. Infrastructure only; business/domain behavior is excluded.
- Branch: `main`; HEAD and `origin/main`:
  `d05c5c4504738d5be0f4f6dbc2900f1b780824d4` (`MVP_02 fixes`). The Human
  committed/pushed the earlier dirty tree during entry inspection. Reinspection
  found a clean tree (`git status --short`, `git diff --name-status` and
  `git diff --stat` empty). Earlier MVP-02 work is now part of the baseline.
- Shared ERP/authentication shell: `templates/base.html`; login:
  `apps/accounts/templates/accounts/login.html`. Admin extends Django's separate
  `admin/base.html` through `templates/admin/base_site.html` and already uses
  local Django and BONIRA assets. App templates also occur under
  `apps/*/templates/`; fragments/components occur in both template trees.
- The sole remote script/style/font runtime reference found in HTML and
  non-vendor CSS/JS is `https://cdn.tailwindcss.com` in `templates/base.html`.
  No inline Tailwind configuration, Tailwind plugins or existing Node manifest,
  lockfile, Tailwind configuration/input, or frontend build toolchain was found.
- Shared CSS/JS lives in `apps/accounts/static/{css,js}`; app static assets also
  live under projects, workforce, contracts, estimates, billing and daily_reports.
  The substantial inline custom CSS in the base and page templates must remain
  unchanged. Its source position follows the old CDN script; the later browser
  comparison below establishes the effective generated-stylesheet order.
  No custom-CSS relocation is planned.
- Vazirmatn WOFF2 fonts and the BONIRA logo are local under
  `apps/accounts/static/`. Icons are inline SVG. SVG namespace URLs are identifiers,
  not network dependencies. Existing local libraries are Tom Select 2.6.2
  (including its virtual-scroll plugin) and Chart.js 4.6.1; reuse them unchanged.
- Utility classes occur in templates, inline scripts, app static JS
  (`erp_table.js`, `structured-data.js`) and Python widget/presentation definitions.
  Conditional utility alternatives use full class literals. Programmatically
  assembled `erp-badge--{{ status|status_family }}` and organization chart state
  classes are BONIRA custom CSS, not Tailwind utilities. JS toggles such as
  `hidden`, `grid`, `border-blue-500`, `bg-blue-50` are literal and discoverable.
  No interpolated Tailwind color/size utility requiring a safelist was found.
- Django uses `django.contrib.staticfiles`, app-directory finders, `STATIC_URL`
  `static/`, development static serving, and environment-configured production
  `STATIC_ROOT`. No static settings change is planned. Configured PostgreSQL
  connects; one pre-existing unapplied development migration was observed.
  Browser/regression verification will use migrated isolated test databases,
  without migrating or changing the user's development data.

## Intended touch set

- Root `package.json`, `package-lock.json`, `tailwind.config.cjs`, `.gitignore`.
- `frontend/tailwind.css` and generated
  `apps/accounts/static/css/tailwind.css`.
- Replace the CDN script in `templates/base.html` with an ordinary synchronous
  local stylesheet. Preserve the measured effective cascade position in the head.
- README build/deployment instructions; this report and F1-specific verification
  scripts/tests/evidence under `scripts/verification`, `tests`, and `output/f1`.
- No models, migrations, services, views, forms, permission/surface rules,
  business validation, or existing Tom Select/dialog assets are to change.

## Build configuration and measured checks

The minimal toolchain is the official Tailwind v3 CLI (MIT), with one direct
development dependency, exactly `tailwindcss: 3.4.17`, and npm's committed lockfile.
No SPA, bundler, framework, plugin, runtime Node dependency, or duplicate library
was added. Reference: [Tailwind v3 installation](https://v3.tailwindcss.com/docs/installation)
and [content configuration](https://v3.tailwindcss.com/docs/content-configuration).

`tailwind.config.cjs` scans shared templates, app templates, app static JS and
app/core Python. Tests, migrations and vendored JS are excluded; output, historical
evidence, graphify data, media, virtual environments and Node modules are outside
the positive scan roots. Paths resolve relative to the config. Theme/default
breakpoints/preflight remain stock v3, matching the previous unconfigured CDN.
The safelist is empty because existing utilities are full literals. BONIRA's
generated badge/chart classes retain their custom CSS; no broad safelist was used.

- `npm ci --ignore-scripts --no-audit --no-fund`: exit 0; 73 packages installed
  on Windows (the lockfile also retains its optional platform dependency).
- `npm run build:css`: exit 0.
- `npm --offline run build:css`: exit 0; byte-identical SHA-256 before/after:
  `1557718110d6b93881f67e22cdd899a14383474c20640c85d79a535df6957470`.
  Evidence: `output/f1/{npm-ci.txt,build.txt,rebuild-offline.txt,reproducibility.json}`.
- The CLI's stale Browserslist-data advisory is a build-time warning. No dependency
  update was performed; it neither fetches nor loads a runtime resource.
- Temporary-directory `collectstatic` under the existing Django staticfiles
  configuration: 186 assets collected; Tailwind, local font, Tom Select, Chart.js
  and Jalali script match their source bytes. Evidence: `output/f1/collectstatic.json`.
- `python manage.py check`: no issues.

## Failed attempts and attribution

- Initial collection accidentally included an imported existing browser test
  class, so that run was interrupted. The import now uses a module alias.
  Two existing screenshots touched by the attempt were restored byte-for-byte
  from HEAD; no historical evidence change is retained.
- The initial shared-test-DB browser attempt failed during serialized fixture
  restoration: PostgreSQL rejected an UPDATE to an immutable published workflow
  version. It did not reach product/browser verification. Evidence:
  `output/f1/attempt01-shared-db-setup-failed.txt`. Classification: test harness
  setup defect, not a product/build failure. `f1_validate.py` now selects a
  dedicated `test_bonira_f1_20261102` database and empties it before serialized
  snapshot replay, using Django's cascading flush guarded to that exact test DB.
  Database guards and business assertions remain enabled and unchanged.
- Initial F1 harness lint findings (Decimal spelling and explicit subprocess
  `check=False`) were corrected; focused Ruff check and JS syntax check pass.
- First complete-schema Chrome baseline attempt: **FAIL after 49/51 pages**.
  The new network checker treated an existing Tom Select superseded Fetch
  cancellation as a missing asset. The replacement team lookup returned HTTP
  200 and selection succeeded; `field_choices.js` explicitly uses AbortController
  for this behavior. Classification: test harness defect. The checker now
  records URL/cancellation evidence and permits only canceled local choice
  fetches with a successful response from that same endpoint. All actual asset
  failures and failed current lookups still fail. A debounce wait also ensures
  the actual search completes before selection. Tom Select code is unchanged.
  Original evidence: `output/f1/attempt02-before.txt`,
  `output/f1/before/attempt02-{failure.json,command.txt}`, and partial results.
  This run also proves the old CDN resolved to `/3.4.17`.
- The corrected baseline run passed **51/51** pages in installed
  `Chrome/156.0.8078.48` at 1440/1024/390. The first local offline run also passed
  51/51 route/network/interaction checks, but its separate computed visual
  comparison **FAILED**: 47/51 pages differed. No utilities were missing.
  The root cause is CSS cascade position: the CDN appended generated CSS at the
  end of the head, after page styles. A local link at the original script's
  source position instead precedes custom CSS, changing `[hidden]` error
  containers, `.min-h-9` buttons and `.text-sm` helper line heights. The bounded
  correction is to place the synchronous stylesheet last in the head, matching
  the previous effective order; no page CSS, components or behavior are redesigned.
  The initial-order visual evidence is retained separately from the final run.
- Pre-switch baseline `python -m pytest tests/test_filter_bar.py -q`:
  **FAIL, 1 failed / 5 passed**. The failure expects `data-filter-result-count`
  in `components/filter_bar.html`, which no longer renders that attribute.
  The component, helper and assertion are unchanged from the Human's HEAD, and
  the local Tailwind asset was not yet loaded by any page. Classification:
  pre-existing stale UI test (BASELINE TEST DEBT). It is retained unchanged;
  this failed command is not reported as PASS. Evidence:
  `output/f1/filter-components.txt`.
- Pre-switch baseline `python -m pytest
  tests/test_uiux_stage3a.py::PresentationContractsTests -q`:
  **FAIL, 1 failed / 6 passed**. The older Home presentation assertion searches
  for `id="home-start-work"`, absent from the current unchanged Home template.
  Classification: pre-existing stale UI test (BASELINE TEST DEBT), preserved
  without changing current Home/navigation behavior. Evidence:
  `output/f1/shared-presentation.txt`.
- Early discovery commands used a nonexistent login path and PowerShell wildcard
  path syntax incompatible with `rg`; corrected discovery inspected the actual
  template and app paths. A read-only DB diagnostic had a PowerShell quoting
  error; the corrected stdin-based diagnostic succeeded. None mutated product data.

## Final implementation and build proof

The original application/build existing-file touch set is `.gitignore`, `README.md`, and
`templates/base.html`. The base differs from HEAD only by removal of the CDN
script and addition of the normal local stylesheet and its ordering comment at
the end of the head. All page/component/custom CSS, shared JS, Tom Select,
Chart.js, fonts, forms, views, models, migrations, services, workflows, validation,
permissions, tenant/project/site scope and Product Surface rules are unchanged.

New files: `package.json`, `package-lock.json`, `tailwind.config.cjs`,
`frontend/tailwind.css`, generated `apps/accounts/static/css/tailwind.css`,
`scripts/verification/f1_{browser.mjs,assets.cjs,compare.cjs,validate.py}`,
`tests/test_f1_offline_browser.py`, this report, and `output/f1/` evidence.

- Build environment: Node `v24.20.0`, npm `11.19.0`, Windows; Django `5.2.17`
  with PostgreSQL/Psycopg 3. All 447 repository migrations applied in the isolated
  test database. The pre-existing development migration remains untouched.
- Manifest, lockfile and installed module: **exactly 3.4.17**. Final minified CSS:
  **36,643 bytes**, SHA-256
  `1557718110d6b93881f67e22cdd899a14383474c20640c85d79a535df6957470`.
  The final offline rebuild after the head-order correction also matches these
  bytes (`output/f1/final-build.txt`).
- Content scan: **935 sources: 377 HTML, 18 JS, 540 Python**. No generated
  output/evidence, test, migration or vendor source was scanned. Of 448 distinct
  rendered classes, **234 are recognized Tailwind utilities; all are compiled**.
  The complete compiled asset has 569 class selectors for the broader source
  surface. Missing utilities: **0**; safelist: **empty**.
  [Coverage proof](../../../output/f1/dynamic-coverage.txt).
- Active runtime audit: **969 sources**, **zero** prohibited Tailwind CDN
  references. Remaining literal host mentions are documentation/history or the
  verification driver's before-state allowlist; they are not normal application
  runtime dependencies. Existing source/hash and exact base-edit checks pass.
  [Source audit](../../../output/f1/source-audit.json).
- Build/install/watch/production collection commands are documented in the
  [README](../../../README.md#local-frontend-assets-tailwind-css-3417). Normal
  serving requires no Node.js or internet access after building/collecting assets.

## Final Chrome/offline/network verification

**PASS — 51 page/viewport combinations**, installed
`C:\Program Files\Google\Chrome\Application\chrome.exe`, reported
`Chrome/156.0.8078.48`, at **1440, 1024 and 390** CSS pixels, 900px viewport height.
Each width covers these 17 real MVP routes with explicitly authorized synthetic
tenant data and no hidden-surface activation:

| Area | Screens |
| --- | --- |
| Foundation | anonymous login, authenticated Home/shell/navigation |
| Projects | Projects List, Project Detail with local Chart.js |
| Commercial | Contract List, Contract Detail, Estimate Detail |
| Procurement | PR List/Detail, RFQ List, PO Detail, GRN Detail |
| Inventory | transaction list |
| Operations | workforce list, worker detail, worker form, timekeeping workbench |

The final run used a fresh Chrome profile, cache disabled, service-worker bypass,
global external-host resolution blocked, and Fetch interception permitting only
the exact loopback application origin. A deliberate external fetch to
`offline-proof.invalid` was blocked and recorded before application navigation.
This is a verification-only negative control, not an application dependency.

- Application external requests: **0**; required remote assets: **0**.
- **863** observed responses: 51 Documents, 270 Stylesheets, 330 Scripts,
  201 Fonts, 6 Images, 4 Fetch responses and 1 browser-generated Other request.
- All **51 legitimate documents returned 200**; required assets loaded locally.
- Remaining 404: Chrome's automatic same-origin `/favicon.ico`, classified as
  **browser-generated/non-functional existing behavior**, not a required asset
  or legitimate application route. No required external dependency remains.
- JavaScript exceptions: **0**; console API errors: **0**.
- Every loaded foundation stylesheet is synchronous, local, and last in the head;
  no Tailwind CDN/compiler script, fallback, preload/onload trick or CSS injector.
- Local Vazirmatn is loaded on every page. RTL and no document horizontal
  overflow checks pass on all 51 combinations. Existing internal table scrolling
  remains unchanged.
- Actual interactions: mobile navigation open/close on all 16 authenticated mobile
  screens; Tom Select loopback lookup/selection and Jalali picker opening at all
  three widths. Existing browser journeys additionally exercise filters, row
  menus, forms, approval/history views and chart rendering.

[Network summary](../../../output/f1/network-summary.json),
[complete page measurements](../../../output/f1/offline/results.json),
[probe command result](../../../output/f1/offline/command.txt).
Screenshots are under `output/f1/before/` and `output/f1/offline/`, with each
`<screen>-<width>.png`. Representative final states:
[login](../../../output/f1/offline/login-1440.png),
[Project Detail](../../../output/f1/offline/project-detail-1440.png),
[Contracts tablet](../../../output/f1/offline/contracts-list-1024.png),
[worker form mobile](../../../output/f1/offline/worker-form-390.png),
[GRN](../../../output/f1/offline/grn-detail-1440.png).

## Visual comparison

The corrected head order restores **identical computed styles for all 15,210
sampled body elements** across all 51 combinations. DOM element/class structure
also matches. **48/51** pages have identical measured geometry at the strict
0.1px threshold. The remaining three are GRN Detail at each width: three `bdi`
timestamp strings per page differ because fixtures were created at different
clock times. Their glyph widths/positions differ by **less than 0.5px**, with
identical styling and all other geometry unchanged. Screenshot review confirms
the changed timestamps (12:45 versus 13:04), not a CSS change.

In the original capture the strict diagnostic command returned **FAIL/exit 1**, retained
truthfully in `visual-comparison-summary.txt`; it is not relabeled PASS. Its nine
timestamp-only differences are explicitly attributed in
[visual-attribution.json](../../../output/f1/visual-attribution.json). The measured
CSS/RTL/responsive regression assessment and screenshot review are **PASS**:
no missing utility, redesign, new overflow, badge/form/table/menu or typography
regression remains. The initial real cascade failure and its screenshots/results
remain under `offline-initial-order/` and `initial-order-visual-*`.

## Regression results and attribution — original validation

Commands run through `python scripts/verification/f1_validate.py`, using only
`test_bonira_f1_20261102`. Existing assertions were not modified or weakened.
The runner guards cascading fixture reset to that exact test DB and redirects
existing browser/non-browser evidence into `output/f1/`.

| Run | Actual result | Evidence |
| --- | --- | --- |
| Corrected before-state browser probe | **PASS, 1 test / 51 pages** | `before-pytest.txt` |
| Initial broad focused regression (161 collected methods, with subtests) | **FAIL: 23 failed, 143 passed, 59 subtests passed** | `initial-order-regression.txt`, `.xml`, `regression-inputs.json` |
| Final corrected-order browser batch | **PASS: 8/8 tests** | `final-browser.txt`, `.xml`, `final-browser-inputs.json` |
| Exact HEAD base-template failure replay | **FAIL: 13 failed, 4 passed, 3 subtests passed** | `head-attribution.txt`, `.xml`, `head-attribution-inputs.json` |
| Django check, focused Ruff check/format, JS syntax, whitespace | **PASS** | `django-check.txt`, `ruff-check.txt`, `ruff-format.txt`; final commands |

The broad run covers shared Filter Bar/Home presentation, Projects command
center/business hub, Contracts filters/list components, MVP-02 field workforce
and conformance, MVP-03 Billing/Estimate UI, and MVP-04 PR/PO/GRN/connected
journey checks. The final eight Chrome tests comprise the 51-page offline probe,
both existing MVP-02 conformance browser methods, Project cost-chart rendering,
Contract list interactions, Contract/Billing approval journey, PR journey and
GRN-to-Inventory entry journey. All passed after the cascade correction. Existing
Tom Select code/assets are byte-identical to HEAD.

All **23 broad-suite failure events are attributed**, not hidden or counted as
passes:

- **8 MVP-03 markup/subtest failures**: current contract identity markup, estimate
  form structure, clear-filter attribute adjacency, older titles and empty-state
  copy differ from older assertions. The exact HEAD base-template replay reproduces
  each failure reason. Classification: baseline UI test expectation debt.
- **11 PO fixture/setup failures**: opening approval denies the fixture approver
  `RFQ_QUOTES_APPROVE_OPEN` in `require_business_permission`, before the tested UI
  or CSS is reached. The representative HEAD replay reproduces the same denial;
  the other cases share that setup/authorization stack. Classification: existing
  test infrastructure/fixture debt. Permission enforcement remains fail-closed;
  no grant, scope, protected-operation or business rule was changed to pass tests.
- **2 existing browser failures**: Project advanced-date chip expectations and
  workforce/timekeeping clearing a selected project without the expected URL
  submission. Both reproduce with the exact HEAD template and old CDN, with the
  same failure reasons. Classification: baseline browser behavior/test mismatch,
  left unresolved outside F1 rather than silently changing interactions.
- **2 shared presentation failures**: the pre-switch missing result-count
  attribute and obsolete Home section ID described above, also reproduced with
  HEAD. Classification: baseline stale assertions.

The HEAD replay uses a temporary in-memory template loader; no checkout, branch,
working-tree restoration, assertion change or product-code substitution occurs.
[Per-failure attribution](../../../output/f1/failure-attribution.json) records
**zero unattributed failures**. The raw focused regression command is reported
**FAIL**, since the existing suite is not green. Scoped F1 acceptance is assessed
separately below; this does not convert those failed tests into passes.

Existing tests also wrote `output/mvp-04f/split-lineage.json` and their synthetic
offer PDF at their historical paths. These generated bytes were retained in
`output/f1/initial-order-test-evidence/`; the historical files were restored from
HEAD with original checkout line endings. The same is true of the two earlier
accidentally touched MVP-03 screenshots. Final Git diff has no historical evidence
or report changes. Future F1 harness runs redirect those evidence roots as well.

## Remaining limitations and stop boundary

- The baseline regression/fixture/browser expectation failures above remain.
  F1 does not authorize redesigning those flows or changing permission semantics.
- Strict geometry diagnostics can record live fixture timestamp-content
  differences. The original and remediation evidence and attribution are retained;
  no geometry threshold has been relaxed.
- Verification is on the isolated non-production Django live server, with a
  temporary static collection rehearsal. No production deployment, migration,
  cutover, Human UAT/sign-off or Production Certification was performed.
- Branch and final HEAD/upstream remain `main` /
  `d05c5c4504738d5be0f4f6dbc2900f1b780824d4`. No branch/worktree, staging, commit,
  push, merge, reset, stash or history rewrite was performed. Changes are uncommitted.
- **F2/F3 and MVP-05 were not started.** No Select2, SweetAlert2, Tom Select
  standardization, drawer, navigation/dialog/toast redesign or framework migration.

## F1 remediation — 2026-11-02

### Scope and repository preservation

The remediation request authorizes reproduction/classification and fixes only for
F1-attributable defects. F1 was not reimplemented. Its application template,
Tailwind configuration/input, manifest/lockfile, generated CSS and all existing
application JavaScript remain unchanged from remediation entry. No domain,
permission, fixture-grant, migration, business service or workflow was changed.

Remediation touch set:

- `scripts/verification/mvp02_browser.mjs`: repair a retry synchronization race
  exposed by the faster local asset loading; add failure-state diagnostics.
- `scripts/verification/f1_validate.py` and
  `tests/test_f1_offline_browser.py`: an `F1_EVIDENCE_ROOT` under `output/f1/`
  preserves earlier evidence; record the current test for progress inspection.
- `scripts/verification/f1_compare.cjs`: explicit before/after/output directory
  arguments. Comparison properties and the **0.1px threshold are unchanged**.
- This report and new evidence under `output/f1/remediation-20261102/`.

The Git index became staged during the long validation run outside the agent's
commands. That staging was preserved. The agent did not run `git add`, commit,
push, reset, stash, merge or branch/worktree operations. HEAD and `origin/main`
remain `d05c5c4504738d5be0f4f6dbc2900f1b780824d4`.

### F1-exposed integration defect fixed

The first complete remediation run reproduced a different failure in the
workforce browser test: the retry control disappeared between readiness polling
and the click. An isolated `UX-lookup-retry` run **passed with the exact HEAD
template/CDN** and **failed with local CSS**. Another unchanged-logic diagnostic
repeat passed, confirming an intermittent timing boundary rather than a missing
utility or deterministic application-state failure.

The harness previously accepted **any** Retry button. A focus/preload error or
intermediate render can satisfy that condition before the debounced typed search
has settled; restoring the network at that point can change the dropdown before
the click. The corrected harness keeps the injected fault active until:

1. a non-canceled failed network request matches the exact lookup endpoint and
   typed `q` value;
2. the widget input matches that query, is failed and has `loading === 0`;
3. its Retry control is present.

It then uses the same real Retry click and the same successful-recovery assertion.
Selectors, action expectations, the original 100 × 100ms polling limit, HTTP,
scope, overflow, technical-leakage and business assertions are retained. No
application Tom Select behavior was changed. This is a test synchronization fix,
not a new interaction or a suppressed failure.

The corrected isolated local test passed (**1 collected test**, not three: pytest
deduplicated the repeated CLI node selectors). In the subsequent complete run,
the lookup-error, retry-recovery and catalogue-scroll scenarios passed before
the composite test reached its unchanged, pre-existing clear-filter expectation.
[Fix proof and controls](../../../output/f1/remediation-20261102/harness-fix-proof.json),
[exact harness diff](../../../output/f1/remediation-20261102/harness-fix.diff).

### Complete post-fix regression and per-failure classification

The **entire original F1 focused selection** was rerun after the synchronization
fix, including all representative browser methods, without `-k` exclusions,
skips, xfails, altered business assertions or the targeted-scenario filter.

```text
python scripts/verification/f1_validate.py <all entries in regression-inputs.json> --reuse-db -q
23 failed, 143 passed, 59 subtests passed in 1466.24s
exit=1
```

This command is **FAIL**. Every one of its 23 remaining failure events matches
the retained pre-F1 HEAD failure reason or the identical pre-render authorization
stack already reproduced under HEAD. **Zero** events remain attributable to F1;
**zero** are missing dynamic utilities/safelist failures; **zero** are unclassified.

| Remaining events | Classification | Evidence and disposition |
| --- | --- | --- |
| 8 MVP-03 events | Stale markup/copy or pre-existing view/context-contract expectations | Contract identity markup, estimate action structure, clear-link attribute order, retained sort/context keys, titles and empty-state text match unchanged HEAD behavior. Left unchanged. |
| 2 shared UI events | Stale component/DOM expectations | Result count is no longer inside the Filter Bar; the older Home section ID is absent under HEAD too. Left unchanged. |
| 11 PO events | Pre-existing fixture issue | `AdmissibilityFixtureMixin._make_actor` creates the approver membership without an object-scope grant; `_grant` adds permission only. `approve_quote_opening` correctly denies in `require_business_permission` before the tested page/CSS. The fixture's missing scope was not bypassed or repaired inside F1. |
| 1 Projects browser event | Pre-existing browser-harness issue | The test inserts Gregorian ISO strings into Jalali-enhanced UI inputs and expects the date-filter results/chips. The same step fails with the original HEAD template. No date behavior or assertion was changed. |
| 1 workforce browser event | Pre-existing browser-harness issue | The test expects clearing a selector to navigate automatically. HEAD/current `components/filter_bar.html` uses explicit Apply and `erp_table.js` intentionally suppresses automatic submission in that mode. After the retry fix, this original HEAD failure is reached again. Left unchanged. |

Each individual event, test name, normalized failure reason, classification and
baseline proof is recorded in
[FAILURE_TRIAGE.md](../../../output/f1/remediation-20261102/FAILURE_TRIAGE.md) and
[failure-triage.json](../../../output/f1/remediation-20261102/failure-triage.json).
Raw post-fix [log](../../../output/f1/remediation-20261102/verified-focused.txt),
[JUnit](../../../output/f1/remediation-20261102/verified-focused.xml), and
[exit status](../../../output/f1/remediation-20261102/verified-focused-exit.txt)
remain available. The first remediation run, isolated HEAD/local controls and
pre-fix failure are also retained in that directory.

The eight previously passing representative Chrome methods all passed again in
the **complete post-fix run**, including both MVP-02 conformance methods, local
Chart.js, Contracts/list components, Contract/Billing approval, PR, GRN/Inventory
entry and the 51-page offline probe. Other composite browser/setup failures above
remain real failures: their downstream scenarios are not claimed fully verified.

### Post-fix build, offline and visual verification

- Exact Tailwind **3.4.17**; a fresh local CLI rebuild is byte-identical to the
  served **36,643-byte** asset, SHA-256
  `1557718110d6b93881f67e22cdd899a14383474c20640c85d79a535df6957470`.
  [Build proof](../../../output/f1/remediation-20261102/build-proof.json).
- Runtime Tailwind CDN references: **0**. Source audits confirm no F1 application
  changes during remediation and unchanged application sources behind the
  baseline failures. The test-driver change is shown separately above.
  [Source audit](../../../output/f1/remediation-20261102/source-audit.json).
- Content scan remains **935** sources; all **234/234** observed Tailwind utilities
  are compiled, missing **0**, safelist **empty**.
  [Post-fix coverage](../../../output/f1/remediation-20261102/verified/dynamic-coverage.json).
- Installed **Chrome/156.0.8078.48**, **51/51** page/viewport checks at
  **1440/1024/390**, all legitimate documents **200**, required remote requests
  **0**, required asset errors **0**, JavaScript exceptions/console errors **0**.
  Fresh profiles, disabled cache, service-worker bypass, external DNS blocking
  and the blocked external-fetch negative control were retained. The only
  non-functional error remains the browser-generated local favicon request.
- Local fonts, synchronous last-in-head Tailwind, native/advanced controls,
  Tom Select loopback search/selection, Jalali picker and mobile navigation pass.
  RTL and document overflow checks pass on all 51 cases.
  [Post-fix network/runtime summary](../../../output/f1/remediation-20261102/verified/network-summary.json).
- The first remediation capture matches **all 51** pages' styles and geometry
  under the unchanged strict comparator. After the harness fix, **all 15,210
  elements' styles and structure still match**; geometry matches exactly on 48
  pages. Only the nine GRN timestamp `bdi` nodes differ on the other three pages,
  as live fixture times changed from 12:45 to 16:15. Their text widths change by
  at most **4.47px**; surrounding layout and all styling remain unchanged.
  The post-fix strict diagnostic is still **FAIL/exit 1**, not relabeled PASS.
  [Strict result](../../../output/f1/remediation-20261102/verified/visual-comparison.txt),
  [per-node clock-data attribution](../../../output/f1/remediation-20261102/verified/visual-attribution.json).
  No tolerance or fixture clock was altered to force a pass. Actual desktop,
  tablet and mobile screenshots were inspected; no F1 visual/RTL/responsive
  regression remains.
- Django checks, focused Ruff check/format and JS syntax checks pass. No model,
  migration, permission, workflow, business or Product Surface change was made.

### Scoped acceptance and gate decision

The original F1 regression requirement is to run applicable tests, distinguish
product/build defects from stale tests/harness/fixture/baseline failures, and
never relabel a failed command PASS. Those requirements are now fully evidenced.
The [Execution Policy](../BONIRA_CODEX_PROJECT_EXECUTION_POLICY.md#16-regression-and-baseline-debt-attribution)
also requires evidence-backed baseline attribution and permits scoped completion
when required validation passes **or is validly attributed** (§§15–18).

The earlier report treated the raw baseline suite's redness as an automatic F1
implementation blocker. The current assessment separates these results:

| F1 acceptance boundary | Current result |
| --- | --- |
| Exact local deterministic build; synchronous Django static loading | PASS |
| Runtime CDN/public-internet dependency removal | PASS |
| Content paths and actual dynamic utility coverage | PASS |
| Existing local libraries/Tom Select and business behavior preserved | PASS |
| Representative offline Chrome, RTL/responsive and visual evidence | PASS |
| Complete focused selection executed; every failure classified with baseline evidence | Satisfied; raw command remains FAIL |
| Unresolved F1-attributable defect or unexplained failure | None |

**F1 scoped acceptance: PASS. F1 prerequisite for F2: OPEN.** This does not close
or waive the 23 baseline issues, turn the failed focused command green, claim
full repository regression, accept financial/security residual risk, issue Human
sign-off or authorize production. F2/F3 were not started. Existing staging is
preserved; no agent commit or push was performed.

## Required final verdicts — current scoped assessment

```text
F1 OFFLINE FRONTEND FOUNDATION: PASS
TAILWIND 3.4.17 LOCAL BUILD: PASS
TAILWIND CDN REMOVED FROM RUNTIME: PASS
DYNAMIC CLASS COVERAGE: PASS
LOCAL REQUIRED ASSETS: PASS
OFFLINE RUNTIME: PASS
RTL / RESPONSIVE VISUAL REGRESSION: PASS
EXISTING TOM SELECT PRESERVED: PASS
BUSINESS BEHAVIOR PRESERVED: PASS
BROWSER VALIDATION: PASS
FOCUSED REGRESSION: FAIL
```

```text
F1 REMEDIATION: PASS
FOCUSED REGRESSION: FAIL
OFFLINE RUNTIME: PASS
F1 ENTRY GATE FOR F2: OPEN
```

The local/offline implementation and F1-exposed harness repair are verified.
Baseline failures remain documented and open outside F1. No failed command or
individual failing test is relabeled PASS.
