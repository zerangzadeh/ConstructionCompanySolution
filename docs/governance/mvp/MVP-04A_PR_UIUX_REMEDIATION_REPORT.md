# MVP-04A — Purchase Request Detail UI/UX remediation

**2026-11-02 · PASS within the requested bounded non-production scope.**
**Product Owner visual acceptance: PENDING.**

## Entry, authority and scope

Explicit user request: remediate Purchase Request Detail only, using the three
attached Draft/Submitted/Approved images as visual direction; preserve business
behavior and the accepted F1–F4 foundation; stop afterward; no commit or push.
The F4 conformance report's shared-frontend acceptance was verified before mutation.
Current MVP-04A evidence, UI guidelines, canonical color system, actual PR views,
forms, services, models, routes and shared components were inspected.

Entry/end branch: `main`. HEAD and `origin/main`:
`b97fcc45a92737b83e9c3ffb14b589cfdc4250d7`; divergence 0/0 at entry.
Contrary to the request's description, entry was clean: F1–F4 had already been
checkpointed. This remediation remains uncommitted. Unrelated Contract/Billing
edits appeared concurrently and were preserved without being absorbed into this task.
No CEP lifecycle, Registry, Roadmap, production or Human sign-off event is claimed.

## Actual changed surface

Product files:

- `templates/procurement/request_detail.html` — only the Purchase Request Detail
  page, including its existing validation/decision response renders.
- `apps/accounts/static/css/erp_purchase_request_detail.css` — scoped geometry
  and presentation using existing canonical tokens; no global rule or new color.

The page now consumes the existing local `bonira_tokens.css`; the shared asset
itself is unchanged. Existing status badges, form fields/errors, icons, secondary
request menu styling, table containment and interaction includes are reused.
No product JavaScript, form, view, query/helper, service, model, migration,
permission, lifecycle, financial behavior, Product Surface, Project page or
shared shell/navigation implementation changed.

Verification additions: `tests/test_pr_detail_uiux.py`,
`scripts/verification/pr_detail_uiux_browser.mjs`, this report and
`output/mvp-04a-uiux/`. The local Tailwind rebuild was byte-identical to the
accepted runtime CSS, so it creates no Tailwind product diff.

## State mapping

| State | Resulting presentation | Preserved authority |
| --- | --- | --- |
| Draft | Strong request/project identity; neutral status; four compact summary cards; state guidance and submit CTA; item table beside the entry form at wide desktop and above it at narrower widths; separate red cancellation disclosure | Original item fields, bound errors, minimum-item submission prerequisite, ownership/permission flags, reasons and confirmation endpoints |
| Submitted | Clear awaiting-review guidance; four summary cards; full-width read-only table; primary approve and secondary danger reject disclosures where authorized; concise factual submission history | Existing lifecycle, workflow candidacy, assignment, SoD, transition permissions and required reasons |
| Approved | Success status; next-step guidance; contextual RFQ CTA only when the existing context permits; read-only items; existing RFQ links with compact business-status badges before history | Existing domain, project/tenant permission and Product Surface checks; no automatic RFQ or new relationship |
| Rejected/cancelled | Existing terminal status/reason and no invalid continuation actions | Original terminal-state authority |

All displayed record values come from application records. Browser evidence uses
explicitly synthetic records created through current services in the disposable
test database. Reference sample records were not embedded in product templates.
[Original reference identities](../../../output/mvp-04a-uiux/reference-identity.json).

Intentionally omitted unsupported reference elements:

- PR header edit and persisted item edit/remove: no existing route/service in this
  journey. No replacement mutation path or fictitious row action was invented.
  Consequently edit/remove cannot be exercised as existing browser capabilities.
- PR has project ownership, not a separate Site field; no Site relationship added.
- Future workflow steps, review candidates, sender identity and rejection/
  cancellation timestamps were not inferred. History uses only the record's
  `submitted_at` and `approved_at`; absent timestamps omit their events/section.
- The reference shell/avatar/navigation were not copied or redesigned. Existing
  permission-filtered navigation and Module Selector remain authoritative.

## Functional and affected regression

**23 tests / 9 subtests PASS** in the affected selection, including its browser
fixture. The final stylesheet correction and additional mobile-scroll assertion
were then verified by rerunning that browser fixture: **1/1 PASS**, with all
**14 Chrome cases PASS**. These are 23 distinct selected tests, not 24 distinct
coverage claims. [Affected result](../../../output/mvp-04a-uiux/final-tests.txt),
[JUnit](../../../output/mvp-04a-uiux/final-tests.xml),
[final browser result](../../../output/mvp-04a-uiux/visual-final-tests.txt),
[final browser JUnit](../../../output/mvp-04a-uiux/visual-final-tests.xml).

The selection covers the seven original MVP-04A HTTP tests, three project-workflow
scope tests, four existing atomic workflow/rollback/candidacy/condition checks,
three Module Selector presentation tests, four canonical navigation tests, one
Product Surface navigation test and the new browser fixture.
Original assertions are preserved. No full-repository regression is claimed.
[Exact commands](../../../output/mvp-04a-uiux/commands.txt).

Real installed **Chrome/156.0.8078.48**, headless, actual live Django server and
isolated PostgreSQL `test_bonira_f2_20261102`; existing migrations were applied
when rebuilding this disposable database. No development/customer data mutation
or production migration occurred. Browser matrix: nine owner state/width cases
(three states × 1440/1024/390), three read-only state cases and two independent
project/tenant denial cases.

- Draft at every width: remote material lookup/selection; invalid quantity gives
  the expected 400 with retained material/quantity/description; correction adds a
  real item; submit and approve persist through existing services.
- Submitted: read-only items and factual history; real rejection with required
  reason at every width. Viewer actions are absent. Forged/unauthorized actions,
  tenant/project/material/source isolation and SoD are also covered by HTTP tests.
- Approved: contextual RFQ Create inherits the hidden source; existing RFQ detail
  links resolve; real Back and refresh preserve state without repeated mutation.
- SweetAlert2: existing cancel/submit/approve/reject confirmations; dismissal and
  Escape make no POST, cancellation retains its reason, safe cancel focus, RTL
  and viewport fit; exactly one POST for each confirmed lifecycle action.
- Tom Select: existing remote selector, actual selection/native FormData value,
  bound-error retention and repeated HTMX mount without duplicate wrappers.
- Shared Module Selector: exact server-authorized labels/routes, correct active
  Procurement entry, Escape/focus return and unchanged project/site controls.
- At 390, real horizontal wheel input scrolls the contained table to quantity/
  unit columns; page width stays contained. Entry and primary actions remain usable.

## Offline, console and foundation preservation

Final browser evidence: **1,154 responses**, **15 intended POSTs** (three invalid
item attempts, three corrected additions, three submits, three approvals and
three rejections). **0 JavaScript exceptions, 0 console API errors, 0 application
external requests, 0 unexpected HTTP failures, 0 superseded lookup cancellations.**
External origins are blocked, cache/service workers bypassed, and the external
negative control is proved blocked. No required asset or valid link failed.

Expected HTTP errors remain distinguished: three deliberate invalid-item 400s,
two scope-denial 404s and **one unrelated baseline `/favicon.ico` 404** already
recorded by F4. That favicon failure remains baseline debt; it is not reported
as a successful asset or silently fixed. Browser resource logs are retained.
[Summary](../../../output/mvp-04a-uiux/browser-summary.json),
[complete network/interaction records](../../../output/mvp-04a-uiux/browser/results.json).

- **30/30 inspected foundation source files match HEAD**, including shared shell,
  navigation/context, Product Surface, local vendor assets, tokens, interaction
  scripts and Tailwind configuration/runtime. [SHA evidence](../../../output/mvp-04a-uiux/shared-foundation-source.json).
- Current local Tailwind: **36,643 bytes**, unchanged accepted SHA-256;
  **135/135 required rendered utilities compiled**, zero missing/forbidden scan
  paths, empty safelist. [Coverage](../../../output/mvp-04a-uiux/tailwind-coverage.json).
- Django check: PASS. Focused Ruff check/format, Node syntax, scoped CSS/token
  check, static discovery, UTF-8/mojibake scan and scoped diff whitespace: PASS.
  [System check](../../../output/mvp-04a-uiux/system-check.txt),
  [style conformance](../../../output/mvp-04a-uiux/style-conformance.json).
- No CDN, new select/dialog/navigation implementation, jQuery or dependency added.
  No attributable F1–F4 regression found within this affected verification scope.

## Visual comparison and screenshots

Codex inspected the actual full-page captures against all three supplied images,
including all required widths, selector/validation captures, mobile table scroll
and mobile confirmation. Hierarchy, density, state emphasis, action placement,
read-only table width, entry layout, alignment, status and RTL meet the bounded
visual direction. This is technical visual review, not Product Owner acceptance.

| State | 1440 | 1024 | 390 |
| --- | --- | --- | --- |
| Draft | [Capture](../../../output/mvp-04a-uiux/browser/draft-1440-full.png) | [Capture](../../../output/mvp-04a-uiux/browser/draft-1024-full.png) | [Capture](../../../output/mvp-04a-uiux/browser/draft-390-full.png) |
| Submitted | [Capture](../../../output/mvp-04a-uiux/browser/submitted-1440-full.png) | [Capture](../../../output/mvp-04a-uiux/browser/submitted-1024-full.png) | [Capture](../../../output/mvp-04a-uiux/browser/submitted-390-full.png) |
| Approved | [Capture](../../../output/mvp-04a-uiux/browser/approved-1440-full.png) | [Capture](../../../output/mvp-04a-uiux/browser/approved-1024-full.png) | [Capture](../../../output/mvp-04a-uiux/browser/approved-390-full.png) |

Additional examples: [mobile selector](../../../output/mvp-04a-uiux/browser/draft-390-selector.png),
[retained validation](../../../output/mvp-04a-uiux/browser/draft-390-validation-full.png),
[quantity/unit scrolling](../../../output/mvp-04a-uiux/browser/draft-390-table-scroll.png),
[approval confirmation](../../../output/mvp-04a-uiux/browser/approved-390-confirmation.png).

Visual iteration found and fixed two objective defects before closeout: unloaded
existing token aliases (now loaded locally by this page), and a related-RFQ badge
incorrectly sharing its title's flexible width (now compact). Final captures and
computed-style assertions include both corrections. The initial interaction PASS
was not treated as visual completion.

## Failed attempts and attribution

- Initial browser-test import accidentally collected an unrelated unittest class;
  interrupted, changed to a module alias, and restored this run's three generated
  historical screenshots to exact clean-entry HEAD bytes.
  [Correction record](../../../output/mvp-04a-uiux/harness-correction.txt).
- The interrupted reused test database polluted serialized workflow replay;
  fixture setup failed at an unchanged immutable-history trigger before any page.
  A fresh disposable test DB rebuild retained all guards and applied existing
  migrations. [Failed setup](../../../output/mvp-04a-uiux/browser-seed-replay-failed.txt).
- The first post-rebuild browser attempt exposed a new test-fixture session bug:
  reusing the viewer Client for another login invalidated its saved cookie. Fixed
  by using a separate Client; no product authentication/authorization change.
  [Failed run](../../../output/mvp-04a-uiux/browser-first-auth-failed.txt).

These failed/interrupted attempts remain failed/interrupted; later PASS results
do not relabel them. No unresolved in-scope product blocker remains.

## Closeout

```text
MVP-04A PR UI/UX REMEDIATION: PASS
DRAFT STATE: PASS
SUBMITTED STATE: PASS
APPROVED STATE: PASS
BUSINESS BEHAVIOR PRESERVED: PASS
PERMISSION / SCOPE PRESERVED: PASS
F1-F4 FRONTEND FOUNDATION PRESERVED: PASS
TOM SELECT CONFORMANCE: PASS
SWEETALERT2 CONFORMANCE: PASS
RESPONSIVE RTL: PASS
TECHNICAL LEAKAGE: PASS
VISUAL REFERENCE CONFORMANCE: PASS
PRODUCT OWNER VISUAL ACCEPTANCE: PENDING
```

Visual UX remediation: READY_FOR_HUMAN_REVIEW. Human sign-off, Production
Certification and production action: NOT EXECUTED. Branch/worktree creation,
staging, commit, push and merge: NOT EXECUTED. Stop after this remediation;
no subsequent MVP package started. Unrelated concurrent work remains untouched.
