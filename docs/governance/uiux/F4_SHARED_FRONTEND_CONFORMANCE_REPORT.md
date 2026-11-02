# F4 — Shared frontend conformance

## Entry and bounded verification (2026-11-02)

- Human authority: focused conformance of F1–F3 only. No new feature, redesign,
  broad/full regression, commit or push. Fix only proved F1–F3 defects; stop
  after F4. No business, schema, workflow, permission, Product Surface or
  tenant/project/site isolation change.
- F3 report read first; its current final gate is
  `F3 ENTRY GATE FOR F4: OPEN`. Current F1/F2 scoped PASS reports also reviewed;
  their attributed failed historical commands remain failures.
- Branch `main`; HEAD/upstream `dfbdfa7686f6fe33a15dfa6a1908c1cf53faa145`,
  zero divergence. Existing uncommitted F2/F3 changes are preserved through the
  entry SHA-256 snapshot in `output/f4/entry-hashes.json`.
- Planned mutation surface: this report, F4-only focused browser fixture/driver
  and evidence under `output/f4/`. Product mutation only if a clear attributable
  defect is reproduced. No such defect is established at entry.
- Representative pages: Projects list, MVP-02 worker create, MVP-03 contract
  create, MVP-04 purchase-request detail; 1440/390. The same Projects route also
  verifies a Projects-only membership. No additional page catalogue.
- Reuse `test_bonira_f2_20261102` through the existing guarded test runner; no
  development data mutation or new schema bootstrap. Browser runtime is restricted
  to its loopback application origin, with external-host negative control.

## Result

**PASS — focused F1/F2/F3 conformance. No product fix or new feature was needed.**
All **187** pre-existing uncommitted source/evidence files retain their entry
SHA-256 hashes. F4 adds only this report, `tests/test_f4_frontend_conformance.py`,
`scripts/verification/f4_browser.mjs` and `output/f4/` verification evidence.
Existing F1–F3 reports, tests, drivers, assets and application code are unchanged.

### Representative scope

Installed **Chrome/156.0.8078.48**, 900px viewport height; **1440 and 390** CSS
pixels. One combined browser journey loads all shared enhancements together:

| Page | Cases | Interaction checked |
| --- | --- | --- |
| Projects list | Authorized actor at both widths | Tailwind/shell and active module drawer |
| MVP-02 worker create | Both widths | Existing Work Team Tom Select and active Workforce drawer |
| MVP-03 contract create | Both widths | Existing Project Tom Select; Party retained; native direction select; active Contracts drawer |
| MVP-04 purchase-request detail | Both widths | Material Tom Select, four existing action confirmations, actual submit/success toast, active Procurement drawer |
| Same Projects list | Projects-only membership at both widths | Authorized entries present; other module entries absent |

**10/10 browser cases PASS.** This is four page types, with the same Projects
route reused for restricted-membership verification. No exhaustive page catalogue,
broad/full regression, hidden capability activation or additional feature work.

## F1 conformance — PASS

- Every page loads exactly one normal, local, synchronous Tailwind stylesheet,
  in the preserved last-in-head cascade position. Loaded CSS rules exist;
  computed `hidden` and `flex` utility probes work. Local Persian fonts load.
  No Tailwind browser compiler, CDN script or runtime internet asset is needed.
- Direct **local** installed CLI rebuild to `output/f4/tailwind-rebuilt.css`
  produces **byte-identical 36,643-byte** CSS without changing the runtime file:
  SHA-256 `1557718110d6b93881f67e22cdd899a14383474c20640c85d79a535df6957470`.
  [Rebuild proof](../../../output/f4/tailwind-reproducibility.json).
- Existing F1 utility checker against the actual F4 rendered class set finds
  **180/180 required utilities compiled**, **0 missing**, **0 forbidden scan
  paths**, safelist **empty**. Current positive content scope: 940 files
  (380 HTML / 20 JS / 540 Python). Generated evidence and vendor sources remain
  excluded. [Coverage proof](../../../output/f4/tailwind-coverage.json).
- Temporary-directory `collectstatic` preserves all **12 selected local assets**
  byte-identically: Tailwind, F2/F3 CSS/JS, Tom Select/plugin, SweetAlert2 and
  Persian font. Both vendor provenance manifests' hashes verify unchanged.
  [Static/source proof](../../../output/f4/static-and-source.json).

## F2 conformance — PASS

- Actual pointer/keyboard remote lookup and selection over loopback succeeds for
  Work Team, Project and Material at both widths. Native values equal `FormData`
  values; original change events fire. Two repeat HTMX mount events leave one
  instance/wrapper. Qualified selectors are enhanced; short native selects stay
  native. Existing Tom Select **2.6.2** and its shared contracts are unchanged.
- The existing local SweetAlert2 **11.26.25** handles purchase-request cancel,
  submit, approve and reject confirmations. Cancel/Escape sends **no POST** and
  retains the entered reason. Approve/reject dismissal sends no decision POST.
  Cancellation receives default keyboard focus; dialogs fit the mobile viewport
  and render in Persian RTL.
- Confirmed submit sends **exactly one POST per width**, to the original endpoint.
  Database assertions prove both synthetic requests finish `submitted`.
  Each response displays the concise local success toast and retains original
  inline server feedback. No business service, form validation, permission,
  workflow, persistent warning or production data was modified.

## F3 conformance — PASS

- Each authenticated shell has one trigger. The drawer's ordered Persian
  labels/routes exactly match independently obtained server navigation context:
  **28 existing entries** for the fully authorized actor and **3** for the
  Projects-only actor (Projects, profile, company selection). It renders no extra
  catalogue or UI-hidden backend entries. Restricted HTTP access to Contract
  create remains **403**; hidden Accounting, Payroll and full-HR routes remain
  unexposed under the existing Product Surface policy.
- Exactly one correct active module appears on each list/create/detail route.
  Native modal focus, forward/reverse Tab wrapping, close button, backdrop,
  Escape, `aria-expanded`, return focus and original background scroll position
  all pass. Background wheel scrolling is blocked while open.
- All modules remain in one horizontal row; real horizontal wheel input moves
  the mobile RTL row. Reduced-motion emulation disables the opening animation.
  Original sidebar/mobile links and project/site control values/disabled states
  are identical before/after drawer interaction. It causes **zero POSTs**;
  the only two POSTs in F4 are the explicitly confirmed synthetic PR submits.
- Canonical Product Surface/navigation authority, organization permission
  context processor, original navigation component and context component/JS are
  unchanged. No tenant/project/site authority or business rule is inferred.

## Offline, console and responsive evidence

Fresh Chrome profile, disabled cache, service-worker bypass, external DNS blocked,
and Fetch interception permitting only the exact loopback application origin.
An intentional external negative control is blocked before application cases.

| Final observation | Result |
| --- | --- |
| Observed responses / successful documents | **262 / 12**, including two post-submit reloads |
| Application external requests / required external assets | **0 / 0** |
| JavaScript exceptions / console API errors | **0 / 0** |
| Unexpected network failures / missing required assets | **0 / 0** |
| Current lookup failures / superseded lookup cancellations | **0 / 0** in this run |
| RTL / local fonts / document overflow / popup fit | **PASS** at 1440 and 390 |
| Browser resource-console errors | **1 unrelated baseline favicon 404**, detailed below |

`Log.entryAdded` is captured in addition to runtime exceptions and console API
calls. The **only** resource-console error is the browser-generated same-origin
`/favicon.ico` **404**, already evidenced before F4 in F1–F3. Classification:
**UNRELATED BASELINE**, not a required frontend asset or an attributable
regression. It remains recorded, not relabeled as a successful resource load.
No other browser log error, required asset failure or application error is waived.

The historical **23 F1 baseline failure events** remain documented in the F1
report. F4 neither reruns that broad selection nor closes those unrelated issues
or changes their failed commands to PASS. The current focused F4 selection has
**zero failing tests** and no unresolved F1/F2/F3-attributable defect.

[Network/console summary](../../../output/f4/network-summary.json),
[complete combined case evidence](../../../output/f4/browser/results.json).

Representative screenshots were visually inspected for legible Persian RTL,
correct controls, responsive flow and fully rendered dialogs/toasts:

- [Desktop worker selector](../../../output/f4/browser/owner-mvp02-worker-1440-selector.png)
- [Mobile contract selector](../../../output/f4/browser/owner-mvp03-contract-390-selector.png)
- [Desktop shared drawer](../../../output/f4/browser/owner-projects-1440-open.png)
- [Restricted mobile drawer](../../../output/f4/browser/restricted-projects-390-open.png)
- [Mobile confirmation](../../../output/f4/browser/owner-mvp04-pr-390-confirmation.png)
- [Mobile success toast](../../../output/f4/browser/owner-mvp04-pr-390-success.png)
- [Mobile Projects layout](../../../output/f4/browser/owner-projects-390-final.png)

## Commands and focused results

Use `.venv/Scripts/python.exe` for Python commands on this workspace.

```text
python scripts/verification/f2_validate.py tests/test_f4_frontend_conformance.py tests/test_f3_module_selector.py::ModuleSelectorPresentationTests core/test_cep017_navigation.py core/test_product_surface.py::SurfacePolicyTests::test_navigation_permissions_empty_groups_and_operational_reports --reuse-db -q --junitxml=output/f4/focused-tests.xml
```

**PASS — 9 tests / 7 subtests**, including the 10-case combined browser test.
The other selected methods cover canonical filtering, active aliases/descendants,
no fabricated entries, unchanged desktop/mobile navigation and existing
permission/exposure intersections. All are directly affected shared-navigation
or frontend boundaries. [Focused result](../../../output/f4/focused-tests.txt).
No failed attempt or assertion weakening occurred in F4.

Additional checks:

- `node node_modules/tailwindcss/lib/cli.js -c tailwind.config.cjs -i frontend/tailwind.css -o output/f4/tailwind-rebuilt.css --minify`: **PASS**, byte-identical.
- `node scripts/verification/f1_assets.cjs output/f4/browser/results.json`: **PASS**, 180/180 utilities.
- Vendor SHA verification and selected-asset temporary `collectstatic`: **PASS**.
- `python manage.py check`: **PASS**, no issues.
- Focused Ruff check/format for the new F4 Python fixture: **PASS**.
- F4 driver `node --check`, report links and `git diff --check`: **PASS**.

## Closeout and acceptance boundary

- Product changes/fixes in F4: **NONE**. Existing F1–F3 implementation, models,
  migrations, business services, permissions, workflows, Product Surface semantics
  and tenant/project/site isolation are preserved.
- All **187/187** entry files remain byte-identical. The separately bounded
  F4 output is verification code, evidence and this report only.
- **Shared frontend foundation: ACCEPTED for the requested representative
  non-production conformance scope.** No full-repository regression, all-page
  readiness, other-browser coverage, Human UAT/sign-off, Production Certification
  or production cutover is claimed. Unrelated baseline debt is retained.
- End branch/HEAD: `main` / `dfbdfa7686f6fe33a15dfa6a1908c1cf53faa145`.
  F2/F3/F4 changes remain uncommitted. No staging, commit, push, merge,
  branch/worktree creation or other Git integration. No CEP Registry lifecycle
  or production event is claimed. **STOP after F4; MVP-05 not started.**

```text
F4: PASS
F1 CONFORMANCE: PASS
F2 CONFORMANCE: PASS
F3 CONFORMANCE: PASS
OFFLINE RUNTIME: PASS
RTL/RESPONSIVE: PASS
F1-F3 ATTRIBUTABLE REGRESSIONS: 0
SHARED FRONTEND FOUNDATION: ACCEPTED
```
