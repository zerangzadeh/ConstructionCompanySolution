# F3 — Shared top module selector drawer

## Entry and scope (2026-11-02)

- Explicit Human F3 authority: shared authenticated-shell drawer only; stop after
  F3; no commit/push. No Product Surface, permission, context, business, page,
  sidebar/mobile-navigation, Tom Select or SweetAlert2 change.
- F2 report read first; current gate: `F2 ENTRY GATE FOR F3: OPEN`.
- Branch `main`; HEAD/upstream `dfbdfa7686f6fe33a15dfa6a1908c1cf53faa145`;
  zero divergence. F2 remains uncommitted and is preserved. Entry source/evidence
  hashes: `output/f3/entry-dirty-hashes.json`.
- Authority: `Agents.md`, Execution Policy, UI Guidelines, existing
  `apps.organizations.context_processors.business_permissions`,
  `core.product_surface.navigation_groups` and canonical navigation metadata.
  This is a separately bounded frontend task, not serial CEP execution.
- Intended product touch set: shared `templates/base.html`, one component,
  local drawer JS/CSS, and a presentation adapter in the existing Product Surface
  template-tag library. No new registry or hardcoded destination catalogue.
- Verification touch set: focused template/browser tests and F3 driver/evidence.
  Reuse the fully migrated disposable F2 test DB through its guarded runner,
  avoiding another full-schema bootstrap. No development data mutation.
- Only Projects, Contracts, Procurement and Workforce representative routes at
  1440/390. No broad regression, F4 or MVP-05.

## Implementation and authority chain

`business_permissions` resolves effective membership permissions, object-scope
availability and existing workspace guards. It calls the canonical
`navigation_groups`, which intersects those inputs with Product Surface.
The drawer consumes that **same request's `product_navigation_groups`**. Its
presentation tag flattens their existing links in canonical order, preserving
Persian labels and reversed real routes. It adds no catalogue, module namespace
map, fallback destination, permission decision or exposure policy. In the tested
MVP configuration the fully authorized actor sees 28 existing destinations;
the Projects-only actor sees exactly 3: Projects, profile and company selection.

Active highlighting first uses the existing `NavigationLink.is_active_for`
route/alias metadata. For a descendant page without an explicit alias, it picks
the longest matching existing destination path **within the already filtered
links**. It cannot add or reveal a denied destination. Focused tests cover
Projects, Contracts, Procurement and Workforce detail paths plus the canonical
Workforce team alias. The sidebar's existing active-state behavior is untouched.

The shared authenticated header has one new grid-icon trigger and a native
`<dialog>` at the viewport top. All entries remain in one nowrap flex row with
horizontal overflow contained inside the drawer. The active entry has
`aria-current="page"`, a blue state and the Persian current-section label.
Opening centers/focuses that entry; an empty authorized list focuses Close and
shows a plain empty state without invented links.

- Close button, actual backdrop click and native Escape all use the same close
  lifecycle: remove the root scroll-lock class, update `aria-expanded`, and
  return focus to the shared trigger without scrolling the page.
- Native modal inertness is retained, with explicit Tab/Shift+Tab wrapping at
  the first/last control. Background HTML/body scrolling is locked only while
  the drawer is open. Existing styles and context inputs are not overwritten.
- Clicking a destination follows its original ordinary link. No form, POST,
  context rewrite, endpoint, module service or client permission system exists.
- The short entrance animation is disabled for `prefers-reduced-motion: reduce`.
  The row and drawer inherit Persian typography and RTL. The grid icon is inline
  SVG; CSS and JS use Django static files. No dependency or external asset added.
- The base template differs from HEAD by **exactly three additive lines**: an
  authenticated local stylesheet, the shared component include, and an
  authenticated local script. Sidebar/mobile-navigation and context-selector
  source/behavior remain unchanged. No page template was edited for F3.

Actual F3 product files:

- `templates/base.html`
- `templates/components/module_selector.html`
- `core/templatetags/product_surface.py` (presentation adapter only)
- `apps/accounts/static/css/erp_module_selector.css`
- `apps/accounts/static/js/erp_module_selector.js`

New verification/evidence files: `tests/test_f3_module_selector.py`,
`scripts/verification/f3_browser.mjs`, this report and `output/f3/`.
No other existing product file was changed by F3. No Tailwind build, package
manifest/lock, model, migration, permission, workflow, business logic, Product
Surface authority, tenant/project/site context, Tom Select or SweetAlert2 change.

## Focused verification and attempt attribution

All commands use `.venv/Scripts/python.exe` on Windows. The existing guarded
`scripts/verification/f2_validate.py` runner reuses only the disposable
`test_bonira_f2_20261102` database. Its complete baseline schema is already
migrated; no new test-DB bootstrap, development migration, production operation,
or mutation of development data was performed. Synthetic test sessions and
memberships are isolated from development data; immutable-history guards remain
enabled. F2 source and evidence files are unchanged.

| Run | Actual result / classification |
| --- | --- |
| [Attempt 01](../../../output/f3/attempt01-focused-tests.txt) | **FAIL: 1 failed, 10 passed, 7 subtests passed**. Browser setup saved the owner's session, then reused the same Django client to log in the restricted actor. Django correctly invalidated the first session; browser navigation redirected to login before reaching the drawer. **TEST INFRASTRUCTURE DEBT**; corrected with a separate client per actor. No product/authentication change. |
| [Attempt 02](../../../output/f3/attempt02-focused-tests.txt) | **FAIL: 1 failed, 10 passed, 7 subtests passed**. The exact-link assertion serialized identical label/URL dictionaries with different key order. **TEST INFRASTRUCTURE DEBT**; normalized construction order, retaining exact ordered label/route comparison. Original screenshot shows the correctly filtered drawer. |
| [Attempt 03](../../../output/f3/attempt03-browser-tests.txt) | **FAIL: 1 browser test**. Installed Chrome moved focus to the document body after Tab from the last native-dialog link. **F3 UX defect**, fixed by explicit boundary Tab/Shift+Tab wrapping. Failure DOM/screenshot retained; this is not classified as baseline debt. |
| [Final browser](../../../output/f3/browser-tests.txt) | **PASS: 1 test / 10 route, actor and viewport cases** after the focused fix. |
| [Final focused selection](../../../output/f3/focused-tests.txt) | **PASS: 10 tests / 7 subtests**. |

Earlier failed commands remain failures. No assertion, server permission guard,
Product Surface rule or existing test was weakened. The resolved F3 UX defect
does not remain as an outstanding F3-attributable regression.

Reproducible focused commands:

```text
python scripts/verification/f2_validate.py tests/test_f3_module_selector.py::ModuleSelectorBrowserTests --reuse-db -q --junitxml=output/f3/browser-tests.xml

python scripts/verification/f2_validate.py tests/test_f3_module_selector.py::ModuleSelectorPresentationTests core/test_cep017_navigation.py core/test_product_surface.py::SurfacePolicyTests::test_navigation_permissions_empty_groups_and_operational_reports core/test_product_surface.py::ProductSurfaceHttpTests::test_permission_and_exposure_are_intersections core/test_product_surface.py::ProductSurfaceHttpTests::test_home_desktop_mobile_and_admin_navigation_share_five_groups --reuse-db -q --junitxml=output/f3/focused-tests.xml
```

The selected tests cover canonical-only labels/routes, absence of unauthorized
and UI-hidden targets, active-route aliases/descendants, no fabricated empty-list
entry, existing desktop/mobile navigation, existing permission/exposure
intersection and the unchanged five navigation groups. No broad regression or
F2 test suite was rerun. There are **11 unique focused test methods**, including
the one browser method, and **7 passing subtests**.

## Browser, visual and offline evidence

Installed **Chrome/156.0.8078.48**, fresh profile, 900px viewport height,
**1440 and 390** CSS pixels:

| Representative route | Authorized actor | Projects-only actor |
| --- | --- | --- |
| Projects list (`projects:list`) | Both widths | Both widths |
| Contracts list (`contracts:list`) | Both widths | Not navigated; absent from restricted drawer |
| Procurement request list (`procurement:request_list`) | Both widths | Not navigated; absent from restricted drawer |
| Workforce list (`workforce:field_list`) | Both widths | Not navigated; absent from restricted drawer |

**10/10 cases PASS.** Each case checks:

- One trigger, initially closed drawer; exact ordered labels/routes against
  independently obtained server navigation context; exactly one correct active
  entry; identical existing sidebar/mobile links before and after interaction.
- Open/focus/modal semantics; one horizontal row; top viewport position;
  close-button, backdrop and Escape dismissal; focus restoration and
  `aria-expanded`; keyboard boundary containment; retained background scroll
  position; blocked background wheel scroll; reduced-motion animation disabled.
- At 390, real horizontal wheel input moves the RTL row. Active entry is brought
  into view. RTL and no document horizontal overflow pass at both widths.
- Context selector values remain identical. Actual drawer links navigate from
  Projects to Contracts at both sizes and update the active entry. All drawer
  interactions produce **zero POSTs**.

The final capture explicitly checks reverse Shift+Tab wrapping as well as
forward Tab, and compares the real `data-context-project` / `data-context-site`
controls (one control in each case, two on Workforce), including disabled state.
The earlier passing capture is retained under `output/f3/pre-final-browser/`.

Reviewed closed/open screenshots include all four route families and the
restricted membership. Representative evidence:

- [Desktop Contracts drawer](../../../output/f3/browser/owner-contracts-list-1440-open.png)
- [Mobile Procurement drawer](../../../output/f3/browser/owner-procurement-request_list-390-open.png)
- [Mobile Workforce drawer](../../../output/f3/browser/owner-workforce-field_list-390-open.png)
- [Restricted mobile drawer](../../../output/f3/browser/restricted-projects-list-390-open.png)
- [Mobile closed shell](../../../output/f3/browser/owner-projects-list-390-closed.png)

Offline verification disables cache, bypasses service workers, blocks external
DNS and intercepts Fetch to allow only the exact loopback application origin.
An intentional external negative control is blocked before application cases.
The final application cases observe **239 responses / 12 successful documents**,
including the two real module-link navigations:

```text
Application external requests / external assets required: 0 / 0
JavaScript exceptions / console API errors: 0 / 0
Failed network loads / required local resource errors: 0 / 0
POSTs from drawer interactions: 0
```

The one inherited browser-generated `/favicon.ico` 404 remains the same
non-functional baseline behavior documented in F1/F2; it is not a required asset
or an F3 regression. No required resource or application error is waived.
[Network summary](../../../output/f3/network-summary.json),
[complete case evidence](../../../output/f3/browser/results.json).

## Preservation, checks and closeout

- **104/104** pre-existing uncommitted F2 source/evidence files retain their
  entry SHA-256 hashes. Canonical `core/product_surface.py`, the organization
  permission context processor and existing navigation component are unchanged.
  Shared base source is the original plus exactly the three declared additions.
  Both new runtime assets collect locally byte-identically.
  [Source/static proof](../../../output/f3/source-and-assets.json).
- Django system check: **PASS**, no issues.
  [Result](../../../output/f3/django-check.txt).
- Focused Ruff check/format: **PASS** for the changed template adapter and new
  F3 Python tests. JS syntax and whitespace checks: **PASS**.
- No outstanding in-scope defect. Other routes, browser engines and production
  behavior were not tested by this representative task; no broader readiness
  claim, Human UAT/sign-off, certification, cutover or risk acceptance is issued.
- End branch/HEAD: `main` / `dfbdfa7686f6fe33a15dfa6a1908c1cf53faa145`.
  F2 and F3 changes remain uncommitted. No branch/worktree creation, staging,
  commit, push, merge or other Git integration. No CEP Registry lifecycle event
  is claimed for this separately bounded frontend task.
- The gate below establishes the F3 prerequisite only. **F4: NOT STARTED.
  MVP-05: NOT STARTED. STOP after F3.**

```text
F3: PASS
PRODUCT SURFACE/PERMISSION FILTERING: PASS
DRAWER UX: PASS
OFFLINE RUNTIME: PASS
F3-ATTRIBUTABLE REGRESSIONS: 0
F3 ENTRY GATE FOR F4: OPEN
```
