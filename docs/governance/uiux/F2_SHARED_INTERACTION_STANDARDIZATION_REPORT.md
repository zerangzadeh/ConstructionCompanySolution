# F2 — Shared interaction standardization

## Entry and bounded touch set (2026-11-02)

- Explicit Human authority: the F2 request in this session; stop after F2,
  no commit/push, F3 or MVP-05. This is bounded frontend work, not CEP execution.
- F1 report read first; its current final verdict is
  `F1 ENTRY GATE FOR F2: OPEN`.
- Entry: `main`, HEAD/upstream `dfbdfa7686f6fe33a15dfa6a1908c1cf53faa145`
  (`f1`), zero divergence, clean working tree. The earlier F1 work has already
  been committed by the Human; no agent Git writes are authorized.
- Rules: `Agents.md`, Execution Policy and UI Guidelines §§28, 39, 47.
- Intended product changes: existing `workforce/field_choices.js` (multiple,
  disabled and HTMX lifecycle preservation), narrowly needed selector CSS;
  local SweetAlert2 vendor JS/CSS/license/provenance; shared opt-in interaction
  JS/CSS and asset includes; purchase-request detail confirmation attributes.
  No models, migrations, permissions, workflows, views, forms, services,
  lookup endpoints, Product Surface or isolation changes.
- Representative browser scope only: MVP-02 worker create, MVP-03 contract
  create, MVP-04 purchase-request detail, at 1440 and 390. Focused F2 browser
  checks and verification scripts/evidence only; no broad regression.

## Implementation

- Reused `SearchChoiceSelect`, its scoped lookup endpoints, Tom Select **2.6.2**,
  virtual-scroll plugin, Persian normalization, selected-option rendering and
  existing event contract. Only explicit `select[data-business-choice]` controls
  mount; short native selects are untouched. No Select2 or jQuery was added.
- The shared initializer now honors native `multiple`, retains the configured
  disabled state through parent changes and cleanup/remount, removes its retry
  and dependency listeners on destruction, and handles direct-element as well
  as container cleanup. Duplicate library/instance guards remain in place.
- Added opt-in local interaction asset includes and a delegated submit handler.
  Purchase-request detail is the sole adopter: existing submit, approve, reject
  and cancel forms receive record/action-specific Persian confirmation text.
  Existing URLs, CSRF, reasons, `novalidate`, conditional permissions and server
  handlers remain unchanged. No new action, transition or endpoint exists.
- Confirmation defaults keyboard focus to **انصراف**. Cancel/Escape/backdrop
  dismissal resumes no submit handler. Confirm calls `requestSubmit` with the
  original submitter, preserving validation, named buttons, `formaction` and
  existing submit handlers. Repeated attempts while a dialog is open are held.
  Without the library, the opt-in handler uses native confirmation; without JS,
  the original server-rendered forms remain usable.
- Only short server success feedback on the adopting page receives a toast;
  its original inline message remains available after dismissal. Field/form
  errors, error messages and persistent business warnings stay inline. No blanket
  conversion of Django messages or page redesign was performed.

### Local dependency qualification

SweetAlert2 **11.26.25** is pinned by vendored files and
[`PROVENANCE.json`](../../../apps/accounts/static/vendor/sweetalert2-11.26.25/PROVENANCE.json).
The upstream [package metadata](https://github.com/sweetalert2/sweetalert2/blob/v11.26.25/package.json)
and [release history](https://github.com/sweetalert2/sweetalert2/releases)
were reviewed. It is actively maintained, MIT licensed (license retained), has
no runtime dependency tree, and supplies accessible keyboard/focus handling.
It fits plain Django forms and delegated HTMX-compatible initialization without
a frontend framework. It can be removed by removing two opt-in includes and
form attributes; the original server contracts remain intact.

Acquisition: `npm pack sweetalert2@11.26.25 --ignore-scripts`, verified against
the registry SHA-512 integrity value. Only standalone `sweetalert2.min.js`
(48,643 bytes; gzip 15,501), separate `sweetalert2.min.css` (30,251 bytes;
gzip 5,034), license and provenance are in Django static assets. The CSS-injecting
`all` build, package development dependencies and CDN loaders are not used.
No root npm manifest/lock change or runtime Node requirement was introduced.
BONIRA overrides use shared tokens, Persian typography, RTL and a viewport-bound
popup width. Styles load through normal local stylesheet links.
The vendor directory's local `.gitattributes` disables text conversion so the
upstream hashes remain stable across Windows/Linux checkouts.

## Verification evidence and attempts

- Environment: dedicated `test_bonira_f2_20261102` PostgreSQL test DB, migration
  and synthetic fixtures only; no development/production data mutation.
  Runner: `scripts/verification/f2_validate.py`. Immutable-history guards remain
  enabled; cascading fixture reset is restricted to this exact disposable DB.
- Asset audit: **PASS** — vendor tarball SHA-512 and selected-file SHA-256
  verification; all six new/changed runtime assets survive temporary-directory
  `collectstatic` byte-identically. The shared base, Tailwind asset, Tom Select
  vendor bytes and Python lookup/widget contract are unchanged against HEAD.
  [Asset proof](../../../output/f2/asset-audit.json).
- First asset-audit attempt: **FAIL**, retained in
  [attempt01-asset-audit.txt](../../../output/f2/attempt01-asset-audit.txt).
  The harness compared working-tree CRLF against Git's normalized LF for the
  unchanged base template. The corrected source check uses Git's normal
  content comparison; collected-byte and vendor-integrity checks remain exact.
- Early F2 harness Ruff findings (Decimal spelling and dict literal) were fixed.
  No product or pre-existing test assertion was changed for those findings.
- Automatic approval review rejected recursive cleanup of the temporary npm
  download directory with `blocked by policy`. It remains in ignored
  `output/f2/vendor/`; runtime provenance is retained separately under static/.
  The only additional infrastructure touch is that narrow `.gitignore` entry.

### Browser capture attempts

- [Attempt 01](../../../output/f2/attempt01-browser-tests.txt): **1 test PASS,
  six page/viewport cases**. Runtime checks passed, but screenshot inspection
  found dialogs captured during their opening fade. Not used for final visual
  acceptance.
- [Focused run / attempt 02](../../../output/f2/focused-tests.txt): **7 tests
  and 4 subtests PASS**. Added an animation wait; desktop captures settled, but
  mobile still caught a not-yet-started opening animation. Its original images
  remain in `output/f2/attempt02-browser/`.
- [Attempt 03](../../../output/f2/attempt03-browser-tests.txt): **FAIL, 1 test**,
  after five completed cases. Requiring settled screenshot opacity exposed a
  separate browser-driver race: the later mobile confirm click was sent during
  a new popup's transform animation. Its request log contains **zero POSTs**,
  JS exceptions, console API errors, external requests or failed resources for
  that case; the confirmed-submit wait timed out. Classification: **TEST
  INFRASTRUCTURE DEBT**, corrected in the F2 driver by waiting for full opacity,
  finished popup animations and two paint frames before modal-button clicks.
  Product code and assertions were unchanged. The failed log, XML, network
  state and screenshots remain under `attempt03-*`; they are not relabeled PASS.
- [Final browser run](../../../output/f2/final-browser-tests.txt): **1 test PASS,
  six cases**, after the driver correction. Fully rendered desktop/mobile
  dialogs and toasts were visually inspected. No further product change or
  broader regression was needed.

## Final representative verification

Installed **Chrome/156.0.8078.48**, 900px viewport height, **1440 and 390** CSS
pixels. Exactly three representative page types were exercised:

| Scope | Page | Real selector |
| --- | --- | --- |
| MVP-02 | Worker create (`workforce:field_create`) | Work team |
| MVP-03 | Contract create (`contracts:create`) | Project; Party retained as the existing shared widget; direction stays native |
| MVP-04 | Purchase-request detail (`procurement:request_detail`) | Material |

**6/6 page/viewport cases PASS.** No page-by-page conversion, hidden capability
activation, broad regression, F3 or MVP-05 was performed.

- Real pointer/keyboard lookup and selection over loopback; values match native
  `FormData`, and original change events fire. Repeat HTMX mount leaves one
  wrapper/instance. Disposable DOM contract probes on the worker page verify
  multiple values, disabled submission omission after dependency reset, and
  direct/container cleanup and remount. Existing native short selects remain
  native. Existing form/server validation and scoping are additionally covered
  by the focused tests below.
- All four adopted action dialogs were exercised. Cancel and Escape produce no
  POST; entered cancellation reason remains in the form. Approve/reject dialog
  dismissal produces no decision POST. Confirmed submit sends **exactly one
  POST per width** to the existing submit endpoint; database assertions prove
  both requests end `submitted`. A DOM probe also verifies required native
  validation before confirmation, original named submitter/`formaction`, deferred
  existing handlers and one submission after repeated attempts.
- RTL, local font loading and no document horizontal overflow pass on all six
  cases. Modal width stays within the viewport, cancellation receives default
  keyboard focus, and the original inline reason/validation controls remain.
  Settled screenshots were reviewed for both sizes, including the modal and
  success toast. Sample final evidence:
  [worker mobile selector](../../../output/f2/browser/mvp02-worker-390-selector.png),
  [contract mobile selector](../../../output/f2/browser/mvp03-contract-390-selector.png),
  [material mobile selector](../../../output/f2/browser/mvp04-pr-390-selector.png),
  [desktop dialog](../../../output/f2/browser/mvp04-pr-1440-confirmation.png),
  [mobile dialog](../../../output/f2/browser/mvp04-pr-390-confirmation.png),
  [mobile success](../../../output/f2/browser/mvp04-pr-390-success.png).
- Offline verification uses a fresh Chrome profile, cache disabled,
  service-worker bypass, external DNS blocked and Fetch interception restricted
  to the exact loopback application origin. An intentional external negative
  control is blocked before the page cases. Application external requests:
  **0**; required external assets: **0**; JS exceptions: **0**; console API
  errors: **0**. **177 responses / 8 successful documents**, including the two
  post-submit reloads. Required local resource errors: **0**.
- Inherited browser-generated `/favicon.ico` **404** remains as in F1; it is
  not a required asset or an F2 regression. Two superseded autocomplete preload
  requests are recorded as canceled, each with a successful response from the
  same endpoint. No actual current lookup or required resource failure is waived.
  [Network summary](../../../output/f2/network-summary.json),
  [complete case evidence](../../../output/f2/browser/results.json).

### Focused commands and results

Use `.venv/Scripts/python.exe` on this Windows workspace.

| Command / selection | Result |
| --- | --- |
| `python scripts/verification/f2_validate.py tests/test_f2_shared_interactions.py <six node IDs from output/f2/focused-inputs.json> --reuse-db -q --junitxml=output/f2/focused-tests.xml` | **7 tests / 4 subtests PASS** |
| `python scripts/verification/f2_validate.py tests/test_f2_shared_interactions.py --reuse-db -q --junitxml=output/f2/final-browser-tests.xml` | **1 test / 6 cases PASS**, final driver |
| Vendor integrity + temporary `collectstatic` audit | **PASS** |
| `python manage.py check` | **PASS**, no issues |
| `ruff check scripts/verification/f2_validate.py tests/test_f2_shared_interactions.py` and `ruff format --check` for those files | **PASS** |
| `node --check` for `erp_interactions.js`, `field_choices.js`, `f2_browser.mjs` | **PASS** |
| `git diff --check` | **PASS** |

The six existing focused methods cover: one native submission control; selected
record retention after validation; stale/cross-project site rejection;
purchase-request item retention and submit/approve handoff; reject/cancel reason
errors and finalized-state actions; cross-tenant creation/material/detail denial.
Exact selections: [focused-inputs.json](../../../output/f2/focused-inputs.json).
No existing test or assertion was modified. No full regression claim is made.
All **447** baseline migrations are applied in the isolated F2 test database;
no migration source or development migration state changed.

## Closeout and boundaries

- Actual existing-file changes: `.gitignore`, shared `field_choices.js` and its
  CSS, and `apps/procurement/templates/procurement/request_detail.html`.
- New files: local vendor directory (JS/CSS/license/provenance/byte-preservation
  attributes), shared `erp_interactions.js`/CSS, two opt-in asset includes,
  `f2_validate.py`, `f2_browser.mjs`, `test_f2_shared_interactions.py`, this report
  and F2 evidence under `output/f2/`. Temporary download scratch is ignored.
- Models, migrations, views, forms, Python business services, lookup scope,
  permissions, workflows, financial behavior and Product Surface: **unchanged**.
  No new business behavior or isolation policy is inferred.
- No unresolved in-scope product defect. Earlier F1 baseline debt remains outside
  F2. Required representative F2 checks pass; broader pages/browsers remain
  untested by design. Human UAT/sign-off and production certification/cutover:
  **NOT EXECUTED**.
- Branch/end HEAD: `main` / `dfbdfa7686f6fe33a15dfa6a1908c1cf53faa145`.
  No branch/worktree created; no `git add`, commit, push, merge or other Git
  integration performed. Changes are uncommitted. No CEP Registry lifecycle
  event is claimed by this separately bounded frontend task.
- The gate below establishes only completion of the F2 prerequisite; it does
  not authorize or start F3. **F3: NOT STARTED. MVP-05: NOT STARTED. STOP after F2.**

```text
F2: PASS
TOM SELECT: PASS
SWEETALERT2: PASS
OFFLINE RUNTIME: PASS
F2-ATTRIBUTABLE REGRESSIONS: 0
F2 ENTRY GATE FOR F3: OPEN
```
