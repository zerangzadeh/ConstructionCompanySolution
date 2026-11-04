# Shared global loading bar — 2026-11-03

Bounded presentation change authorized directly by the user. No backend, route,
Product Surface, permission, workflow, model, migration or dependency changes.
Baseline: local `main`, HEAD `560bc3c9f136a3b76c6816dc127a80d74bcb7a1d`, clean
working tree before discovery. No commit or push.

## Implementation

- `templates/base.html`: central static assets and one component inside the existing
  authenticated application header. Header-free authentication and print layouts
  retain their existing presentation.
- `templates/components/global_loading.html`: named progressbar and polite Persian
  loading announcement; unknown progress has no `aria-valuenow`.
- `apps/accounts/static/css/erp_loading.css`: absolute 3px strip below the sticky
  header border, canonical `--bonira-royal-blue` (#1563D6), RTL/LTR direction,
  restrained animation, static reduced-motion treatment, print exclusion.
- `apps/accounts/static/js/erp_loading.js`: 250ms delay, per-operation tracking,
  idempotent completion, success finish, immediate failure/cancel cleanup,
  abort support and bounded stale-state recovery. No network monkey-patching.

The Navigation API observes document navigation and its success/error/abort
lifecycle without interception. The fallback observes uncancelled link clicks and
form submissions after event propagation, respecting targets/modifier keys,
downloads, hashes and opt-out controls. `pagehide`, `pageshow`, `popstate` and load
hooks clear stale states, including restored browser history entries.

Existing fetch calls populate local form choices; these are deliberately excluded.
The shared shell currently does not load HTMX or implement an asynchronous page
router. Existing HTMX conventions are supported through `htmx:beforeSend` and
`htmx:afterRequest`, plus native XHR `loadend` for detached sources, errors and
aborts. Automatic tracking covers only replacement of `#main-content` or an
ancestor. Component requests can explicitly opt in with
`data-global-loading="true"`; local targets otherwise retain local indicators.
`data-global-loading="false"` on a source/ancestor opts out.

Explicit primary-content work can use the central API:

```javascript
const loading = window.BoniraLoading?.start({signal: controller.signal});
try {
    // Run the existing request and render its result.
    // loading?.progress(percent) only when the producer knows real progress.
    loading?.finish();
} catch (error) {
    loading?.cancel();
    // Preserve the existing error-handling behavior.
    throw error;
}
```

`progress` accepts only finite values from 0 to 100. Multiple simultaneous tasks
use indeterminate presentation because no shared denominator is known. Each task
expires after 120 seconds without a reliable progress update. A producer with a
known longer lifecycle can supply a finite `timeoutMs` and must still finish or
cancel its handle. This timeout changes only presentation, never the request.

## Validation and limits

`manage.py test tests.test_global_loading
tests.test_f3_module_selector.ModuleSelectorPresentationTests --verbosity 1`:
6 tests PASS. The loading test invokes installed headless Chrome against the real
Django-rendered shared layout and real local HTTP/XHR requests. No database access
or writes are used. Its scenario groups cover fast/slow navigation, overlap,
actual determinate input, failure/abort, stale timeout, HTMX primary/local target
selection, back/forward, downloads/hashes, cancelled submissions, retained local
form feedback, reduced motion, and desktop/mobile geometry.

JavaScript syntax, Ruff check/format and `git diff --check`: PASS. Django system
checks: no issues. Evidence: `output/global-loading/results.json`,
`output/global-loading/rtl-1440.png`, `output/global-loading/rtl-390.png`.
Both captures visually reviewed: correct header placement, restrained blue strip,
RTL alignment and no overflow. Browser geometry confirms unchanged main-content
bounds while the bar appears.

Browser evidence uses an isolated shell fixture with synthetic Persian content,
not production/tenant data or a full domain journey. HTMX events are dispatched
against real XHR because the shell does not currently ship HTMX. Other browser
engines have not been exercised; the fallback was tested in Chrome with its
Navigation API disabled. Local submission feedback is verified with fixture
controls, not every domain's form. No existing local loading handlers changed.

Browsers cannot preserve/finish an animation across destruction of the old document;
the new document starts hidden. Initial server response time before any document
JavaScript exists cannot be indicated. Fallback browsers cannot reliably observe
browser Stop, native `form.submit()`, script-driven location changes, or unlabelled
server attachment responses; missing lifecycle events expire through the watchdog.
Unrelated fetch/XHR requests require explicit opt-in if they later affect primary
content. Failure handling adds no error UI and leaves existing feedback intact.

VISUAL UX REMEDIATION: READY_FOR_HUMAN_REVIEW

PRODUCT OWNER VISUAL ACCEPTANCE: PENDING
